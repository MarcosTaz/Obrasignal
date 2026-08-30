from pathlib import Path

SURFACE = Path('mobile/components/AccountPrivacyControls.js')


def test_unknown_deletion_state_remains_private_locked_but_recovery_retry_is_allowed():
    source = SURFACE.read_text(encoding='utf-8')

    # Server recovery contract proves UNKNOWN can be converted to a known PENDING
    # state by repeating the destructive request. The client must keep private UI
    # locked while still allowing that exact-confirmation recovery path.
    assert "const shouldLock = next?.state !== 'NONE'" in source
    assert "status?.state === 'UNKNOWN'" not in source.split('const deletionBlocked =', 1)[1].split('\n', 1)[0]
    assert 'confirmation !== DELETE_CONFIRMATION' in source
