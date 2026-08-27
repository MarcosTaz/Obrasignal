from __future__ import annotations

from .seed_primary import build_primary
from .seed_secondary import build_secondary


def build_seed_companies(observed_at: str):
    return build_primary(observed_at) + build_secondary(observed_at)
