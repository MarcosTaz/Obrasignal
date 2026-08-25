"""Secret-free configuration governance contracts for ObraSignal.

This module is deliberately metadata-only: it records configuration names and
semantics, never secret values. Domain owners remain authoritative for feature,
provider, authentication, billing, notification, and source behavior.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ConfigKeyContract:
    name: str
    owner: str
    value_type: str
    required_environments: tuple[str, ...]
    safe_default: str | None
    visibility: str
    consumers: tuple[str, ...]
    semantic_effect: str
    failure_behavior: str
    source_of_truth: str
    aliases: tuple[str, ...] = ()


MOBILE_NODE_VERSION = "22.13.1"
MOBILE_NODE_WORKFLOWS = (
    ".github/workflows/quality.yml",
    ".github/workflows/web-preview.yml",
    ".github/workflows/mobile-release-preflight.yml",
    ".github/workflows/eas-preview.yml",
    ".github/workflows/eas-production.yml",
)

CONFIG_REGISTRY: dict[str, ConfigKeyContract] = {
    "EXPO_PUBLIC_SUPABASE_URL": ConfigKeyContract(
        name="EXPO_PUBLIC_SUPABASE_URL",
        owner="Auth/Mobile",
        value_type="url",
        required_environments=("MOBILE_DEV_BUILD", "MOBILE_RELEASE_BUILD", "WEB_PREVIEW"),
        safe_default=None,
        visibility="PUBLIC",
        consumers=("mobile/lib/supabase.ts", ".github/workflows/web-preview.yml"),
        semantic_effect="selects the Supabase project used by the public client",
        failure_behavior="client initialization must fail when absent",
        source_of_truth="environment/build configuration",
    ),
    "EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY": ConfigKeyContract(
        name="EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
        owner="Auth/Mobile",
        value_type="string",
        required_environments=("MOBILE_DEV_BUILD", "MOBILE_RELEASE_BUILD", "WEB_PREVIEW"),
        safe_default=None,
        visibility="PUBLIC",
        consumers=("mobile/lib/supabase.ts", ".github/workflows/web-preview.yml"),
        semantic_effect="selects the public Supabase client credential",
        failure_behavior="client initialization must fail when absent",
        source_of_truth="environment/build configuration",
    ),
    "EXPO_PUBLIC_API_URL": ConfigKeyContract(
        name="EXPO_PUBLIC_API_URL",
        owner="API/Mobile/Web",
        value_type="url",
        required_environments=("MOBILE_DEV_BUILD", "MOBILE_RELEASE_BUILD", "WEB_PREVIEW"),
        safe_default=None,
        visibility="PUBLIC",
        consumers=("mobile/src/api.js", ".github/workflows/web-preview.yml"),
        semantic_effect="selects the API target baked into the client",
        failure_behavior="must not silently select another environment",
        source_of_truth="environment/build configuration",
    ),
    "EXPO_PUBLIC_REVENUECAT_ANDROID_KEY": ConfigKeyContract(
        name="EXPO_PUBLIC_REVENUECAT_ANDROID_KEY",
        owner="Billing/Mobile",
        value_type="string",
        required_environments=("MOBILE_RELEASE_BUILD",),
        safe_default=None,
        visibility="PUBLIC",
        consumers=("mobile/src/billing.js",),
        semantic_effect="configures the Android RevenueCat public SDK client",
        failure_behavior="billing capability must not report configured when absent",
        source_of_truth="EAS environment/build configuration",
    ),
    "EXPO_PUBLIC_REVENUECAT_IOS_KEY": ConfigKeyContract(
        name="EXPO_PUBLIC_REVENUECAT_IOS_KEY",
        owner="Billing/Mobile",
        value_type="string",
        required_environments=("MOBILE_RELEASE_BUILD",),
        safe_default=None,
        visibility="PUBLIC",
        consumers=("mobile/src/billing.js",),
        semantic_effect="configures the iOS RevenueCat public SDK client",
        failure_behavior="billing capability must not report configured when absent",
        source_of_truth="EAS environment/build configuration",
    ),
    "OBRASIGNAL_AUTH_MODE": ConfigKeyContract(
        name="OBRASIGNAL_AUTH_MODE",
        owner="Auth",
        value_type="enum(development,provider)",
        required_environments=("PRODUCTION",),
        safe_default=None,
        visibility="PUBLIC",
        consumers=("auth_context.py", "auth_context_jwt.py", "render.yaml"),
        semantic_effect="selects development identity or provider-verified authentication",
        failure_behavior="missing production-capable mode must fail closed; tracked by #451",
        source_of_truth="runtime environment; production blueprint declares provider",
    ),
    "OBRASIGNAL_JWT_ISSUER": ConfigKeyContract(
        name="OBRASIGNAL_JWT_ISSUER",
        owner="Auth",
        value_type="url",
        required_environments=("PRODUCTION",),
        safe_default=None,
        visibility="PUBLIC",
        consumers=("auth_context_jwt.py", "render.yaml"),
        semantic_effect="selects the JWT issuer/project trusted by provider auth",
        failure_behavior="provider auth must fail closed when absent or malformed",
        source_of_truth="runtime environment",
    ),
    "OBRASIGNAL_DB": ConfigKeyContract(
        name="OBRASIGNAL_DB",
        owner="Persistence",
        value_type="path",
        required_environments=("PRODUCTION",),
        safe_default=None,
        visibility="PUBLIC",
        consumers=("render.yaml",),
        semantic_effect="selects the canonical persistence path",
        failure_behavior="production must not silently select a fixture/test database",
        source_of_truth="runtime environment",
    ),
}

KNOWN_CONFIG_DEBT = {
    "AUTH_MODE_MISSING_FAILS_OPEN": {
        "owner": "Auth/Security",
        "classification": "SECURITY_RELEVANT",
        "issue": 451,
    },
    "MOBILE_DEPENDENCIES_WITHOUT_LOCKFILE": {
        "owner": "Config/Release/Mobile",
        "classification": "BUILD_RELEVANT",
        "issue": None,
    },
    "EAS_CLI_LATEST": {
        "owner": "Config/Release",
        "classification": "BUILD_RELEVANT",
        "issue": None,
    },
}


def contract_fingerprint() -> str:
    """Return a deterministic fingerprint of secret-free contract metadata."""
    payload = {
        "mobile_node_version": MOBILE_NODE_VERSION,
        "registry": {name: asdict(CONFIG_REGISTRY[name]) for name in sorted(CONFIG_REGISTRY)},
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
