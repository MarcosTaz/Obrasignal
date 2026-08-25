import finland_runtime


def test_finland_runtime_installer_is_available():
    assert callable(finland_runtime.install)
    assert finland_runtime.SOURCE == "FI_HILMA"
