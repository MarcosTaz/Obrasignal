"""Small fail-closed runtime rollout policy for registered capabilities.

The capability registry is declarative.  This module is the explicit runtime
boundary that turns registry lifecycle + environment configuration into a
single deterministic enable/disable decision without inventing a service
framework.
"""
from __future__ import annotations

import os
import re
from collections.abc import Mapping

from capability_registry import capability

_TRUE = frozenset({"1", "true", "yes", "on", "enabled"})
_FALSE = frozenset({"0", "false", "no", "off", "disabled"})


def _env_key(prefix: str, flag: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", str(flag).strip()).strip("_").upper()
    if not normalized:
        raise RuntimeError("capability feature flag name is invalid")
    return f"{prefix}_{normalized}"


def _configured_bool(environ: Mapping[str, str], key: str) -> bool | None:
    raw = environ.get(key)
    if raw is None or not str(raw).strip():
        return None
    value = str(raw).strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    # Ambiguous rollout configuration must never enable a capability.
    raise RuntimeError(f"invalid boolean capability configuration: {key}")


def rollout_keys(name: str) -> tuple[str | None, str | None]:
    """Return the feature and kill-switch environment keys for a capability."""
    spec = capability(name)
    if not spec.feature_flag:
        return None, None
    return (
        _env_key("OBRASIGNAL_FEATURE", spec.feature_flag),
        _env_key("OBRASIGNAL_KILL", spec.feature_flag),
    )


def runtime_enabled(name: str, *, environ: Mapping[str, str] | None = None) -> bool:
    """Resolve one capability's runtime state.

    Rules are deliberately conservative:
    - RESEARCH/DISABLED/DEPRECATED never run from a flag alone;
    - EXPERIMENT/PILOT require an explicit true feature flag;
    - ENABLED runs by default, but an explicit false feature flag may disable it;
    - a true kill switch always wins;
    - malformed configuration raises instead of silently enabling anything.
    """
    spec = capability(name)
    env = os.environ if environ is None else environ

    if spec.state in {"RESEARCH", "DISABLED", "DEPRECATED"}:
        return False

    feature_key, kill_key = rollout_keys(name)
    if feature_key is None:
        return spec.state == "ENABLED"

    kill = _configured_bool(env, kill_key) if kill_key else None
    if kill is True:
        return False

    feature = _configured_bool(env, feature_key)
    if spec.state in {"EXPERIMENT", "PILOT"}:
        return feature is True
    if spec.state == "ENABLED":
        return feature is not False
    return False
