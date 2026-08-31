from pathlib import Path

SURFACE = Path('mobile/components/AccountPrivacyControls.js')


def test_failed_deletion_remains_private_shell_locked_but_retryable():
    source = SURFACE.read_text(encoding='utf-8')

    # FAILED means prior cleanup was not completed. Private data must stay hidden,
    # but the backend deliberately supports retry after a deletion_failed state.
    assert "const privacyLocked" not in source  # state is React-managed, not derived here
    assert "status?.state === 'FAILED'" not in source.split('const deletionBlocked =', 1)[1].split('\n', 1)[0]
    assert "next?.state !== 'NONE'" in source


def test_retry_still_requires_exact_destructive_confirmation():
    source = SURFACE.read_text(encoding='utf-8')
    assert "confirmation !== DELETE_CONFIRMATION" in source
    assert "DELETE_MY_OBRASIGNAL_DATA" in source
