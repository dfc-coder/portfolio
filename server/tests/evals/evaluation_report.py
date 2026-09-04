from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def report_metadata(
    *,
    dataset: Path,
    candidate_id: str,
    model: str,
    generation_config: dict[str, Any] | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "git_commit": git_commit(),
        "dataset": str(dataset),
        "dataset_hash": sha256_file(dataset),
        "candidate_id": candidate_id,
        "model": model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if generation_config is not None:
        metadata["generation_config"] = generation_config
    if seed is not None:
        metadata["seed"] = seed
    return metadata
