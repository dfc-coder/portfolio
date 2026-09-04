from __future__ import annotations

import json
from pathlib import Path
from typing import Any

Profile = dict[str, Any]


def load_profile(path: Path) -> Profile:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("business profile must be a JSON object")
    return data


def profile_name(profile: Profile) -> str:
    owner = profile.get("owner")
    if not isinstance(owner, dict) or not isinstance(owner.get("name"), str):
        raise ValueError("business profile is missing owner.name")
    return owner["name"]
