from __future__ import annotations

import asyncio
import ipaddress
import json
import time
from collections import deque

from starlette.types import ASGIApp, Message, Receive, Scope, Send


_BODY_METHODS = {"POST", "PUT", "PATCH"}
_PROTECTED_PREFIX = "/v1/"
_STREAM_PATH = "/v1/chat/stream"


class EdgeSecurityMiddleware:
    """Small in-process guard for the public HTTP edge.

    This is intentionally process-local: the portfolio backend runs as one API process.
    The global limits remain effective even if a client attempts to spoof forwarded IPs.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_request_bytes: int = 16_384,
        requests_per_window: int = 10,
        global_requests_per_window: int = 60,
        window_seconds: int = 60,
        max_streams_per_client: int = 2,
        max_global_streams: int = 4,
        trust_proxy_headers: bool = False,
    ) -> None:
        self._app = app
        self._max_request_bytes = max(1, max_request_bytes)
        self._requests_per_window = max(1, requests_per_window)
        self._global_requests_per_window = max(1, global_requests_per_window)
        self._window_seconds = max(1, window_seconds)
        self._max_streams_per_client = max(1, max_streams_per_client)
        self._max_global_streams = max(1, max_global_streams)
        self._trust_proxy_headers = trust_proxy_headers
        self._lock = asyncio.Lock()
        self._client_requests: dict[str, deque[float]] = {}
        self._global_requests: deque[float] = deque()
        self._active_streams: dict[str, int] = {}
        self._global_active_streams = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        method = str(scope.get("method", "GET")).upper()
        path = str(scope.get("path", ""))
        is_protected = path.startswith(_PROTECTED_PREFIX) and method != "OPTIONS"
        is_stream = path == _STREAM_PATH and method == "POST"
        client_key = self._client_key(scope)
        stream_acquired = False

        if method in _BODY_METHODS and self._content_length(scope) > self._max_request_bytes:
            await self._reject(send, 413, "request_too_large")
            return

        if is_protected:
            rejection = await self._admit(client_key, is_stream)
            if rejection is not None:
                await self._reject(send, 429, rejection, retry_after=self._window_seconds)
                return
            stream_acquired = is_stream

        try:
            guarded_receive = receive
            if method in _BODY_METHODS:
                body = await self._read_body(receive)
                if body is None:
                    await self._reject(send, 413, "request_too_large")
                    return
                guarded_receive = self._replay_body(body, receive)

            await self._app(scope, guarded_receive, self._secure_send(send))
        finally:
            if stream_acquired:
                await self._release_stream(client_key)

    async def _admit(self, client_key: str, is_stream: bool) -> str | None:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        async with self._lock:
            self._prune(self._global_requests, cutoff)
            if len(self._global_requests) >= self._global_requests_per_window:
                return "global_rate_limit"

            client_requests = self._client_requests.get(client_key)
            if client_requests is not None:
                self._prune(client_requests, cutoff)
                if not client_requests:
                    self._client_requests.pop(client_key, None)
                    client_requests = None
            if client_requests is not None and len(client_requests) >= self._requests_per_window:
                return "client_rate_limit"

            if is_stream:
                if self._global_active_streams >= self._max_global_streams:
                    return "global_stream_limit"
                if self._active_streams.get(client_key, 0) >= self._max_streams_per_client:
                    return "client_stream_limit"

            if client_requests is None:
                client_requests = deque()
                self._client_requests[client_key] = client_requests
            client_requests.append(now)
            self._global_requests.append(now)

            if is_stream:
                self._active_streams[client_key] = self._active_streams.get(client_key, 0) + 1
                self._global_active_streams += 1

        return None

    async def _release_stream(self, client_key: str) -> None:
        async with self._lock:
            remaining = self._active_streams.get(client_key, 1) - 1
            if remaining > 0:
                self._active_streams[client_key] = remaining
            else:
                self._active_streams.pop(client_key, None)
            self._global_active_streams = max(0, self._global_active_streams - 1)

    async def _read_body(self, receive: Receive) -> bytes | None:
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return b""
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self._max_request_bytes:
                return None
            if chunk:
                chunks.append(chunk)
            if not message.get("more_body", False):
                return b"".join(chunks)

    @staticmethod
    def _replay_body(body: bytes, receive: Receive) -> Receive:
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        return replay

    @staticmethod
    def _prune(events: deque[float], cutoff: float) -> None:
        while events and events[0] <= cutoff:
            events.popleft()

    def _client_key(self, scope: Scope) -> str:
        if self._trust_proxy_headers:
            forwarded = self._header(scope, b"x-forwarded-for")
            if forwarded:
                # A trusted reverse proxy may append to an existing X-Forwarded-For
                # chain. Prefer the right-most valid address over caller-controlled left entries.
                for candidate in reversed(forwarded.split(",")):
                    normalized = self._normalize_ip(candidate.strip())
                    if normalized is not None:
                        return normalized

        client = scope.get("client")
        if client:
            normalized = self._normalize_ip(str(client[0]))
            if normalized is not None:
                return normalized
            return str(client[0])
        return "unknown"

    @staticmethod
    def _normalize_ip(value: str) -> str | None:
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            return None

    @staticmethod
    def _header(scope: Scope, name: bytes) -> str | None:
        for key, value in scope.get("headers", []):
            if key.lower() == name:
                return value.decode("latin-1")
        return None

    @classmethod
    def _content_length(cls, scope: Scope) -> int:
        value = cls._header(scope, b"content-length")
        if value is None:
            return 0
        try:
            return max(0, int(value))
        except ValueError:
            return 0

    @staticmethod
    def _secure_send(send: Send) -> Send:
        async def wrapped(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {key.lower() for key, _ in headers}
                for key, value in (
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                ):
                    if key not in existing:
                        headers.append((key, value))
                message = {**message, "headers": headers}
            await send(message)

        return wrapped

    @staticmethod
    async def _reject(
        send: Send,
        status_code: int,
        code: str,
        *,
        retry_after: int | None = None,
    ) -> None:
        body = json.dumps({"detail": code}, separators=(",", ":")).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"cache-control", b"no-store"),
            (b"x-content-type-options", b"nosniff"),
        ]
        if retry_after is not None:
            headers.append((b"retry-after", str(retry_after).encode("ascii")))
        await send({"type": "http.response.start", "status": status_code, "headers": headers})
        await send({"type": "http.response.body", "body": body})
