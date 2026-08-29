from factory_cloud.factory_switchboard import load_switchboard, start_packet


def test_factory_cloud_global_command_is_d():
    switchboard = load_switchboard()
    packet = start_packet("factory-cloud", switchboard)

    assert packet["signal"] == "D"
    assert packet["payload"].startswith("D — RESUME THE EXISTING FACTORY")
    assert "Ω" not in packet["payload"]
