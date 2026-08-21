from __future__ import annotations

import json
from pathlib import Path

from app.domain.profile import BusinessProfile


def load_business_profile(path: Path) -> BusinessProfile:
    with path.open("r", encoding="utf-8") as handle:
        return BusinessProfile.model_validate(json.load(handle))
