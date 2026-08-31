"""Run the live A/B isolation probe with a real ephemeral Supabase tenant B.

The canonical probe remains unchanged. When permanent B credentials are absent,
the workflow provisions an authenticated anonymous Supabase session and this
adapter injects that session as tenant B. All distinct-user and isolation
assertions in the canonical probe still execute unchanged.
"""
import os

import live_tenant_isolation_e2e as probe

_token_b = os.environ.get("E2E_ACCESS_TOKEN_B", "").strip()
_user_id_b = os.environ.get("E2E_USER_ID_B", "").strip()

if _token_b or _user_id_b:
    if not (_token_b and _user_id_b):
        raise SystemExit("FAIL: incomplete ephemeral tenant B session")
    _original_sign_in = probe.sign_in
    # Satisfy the canonical precondition that a second identity source exists;
    # sign_in below supplies the actual provider-authenticated identity.
    probe.EMAIL_B = "ephemeral-provider-session"
    probe.PASSWORD_B = "ephemeral-provider-session"

    def _sign_in(email, password, label):
        if label == "B":
            return {"label": "B", "token": _token_b, "id": _user_id_b}
        return _original_sign_in(email, password, label)

    probe.sign_in = _sign_in


if __name__ == "__main__":
    try:
        probe.main()
    except probe.TestFailure as exc:
        print(f"FAIL: {exc}", file=__import__("sys").stderr)
        raise SystemExit(1)
