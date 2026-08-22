from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.profile import BusinessProfile
from app.infrastructure.config.profile_loader import load_business_profile


@pytest.fixture
def profile() -> BusinessProfile:
    path = Path(__file__).resolve().parents[1] / "config" / "business-profile.json"
    return load_business_profile(path)
