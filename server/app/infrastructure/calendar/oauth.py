from __future__ import annotations

import asyncio
import time

import httpx


class GoogleOAuthTokenProvider:
    def __init__(
        self,
        client: httpx.AsyncClient,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> None:
        self._client = client
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._access_token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def access_token(self) -> str:
        async with self._lock:
            if self._access_token and time.monotonic() < self._expires_at - 60:
                return self._access_token

            response = await self._client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "refresh_token": self._refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            payload = response.json()
            self._access_token = payload["access_token"]
            self._expires_at = time.monotonic() + int(payload.get("expires_in", 3600))
            return self._access_token
