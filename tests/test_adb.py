from android_device_agent.adb import parse_devices


def test_parse_devices() -> None:
    output = """List of devices attached\nABC123 device product:foo model:HONOR_Test device:test transport_id:1\n192.168.1.88:5555 offline product:bar model:Pixel_8 transport_id:2\n"""
    devices = parse_devices(output)
    assert devices[0]["serial"] == "ABC123"
    assert devices[0]["state"] == "device"
    assert devices[0]["model"] == "HONOR_Test"
    assert devices[1]["serial"] == "192.168.1.88:5555"
    assert devices[1]["state"] == "offline"
