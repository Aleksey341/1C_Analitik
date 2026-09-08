from meeting_bridge.devices import resolve_from_maps, same_device_warning


def test_resolve_mic_by_substring():
    mic = [{"index": 1, "name": "Головной телефон HONOR", "is_loopback": False}]
    loop = [{"index": 2, "name": "Наушники HONOR [Loopback]", "is_loopback": True}]
    got = resolve_from_maps("Honor", "mic", mic, loop)
    assert got["index"] == 1


def test_resolve_loopback_by_substring():
    mic = [{"index": 1, "name": "Головной телефон HONOR", "is_loopback": False}]
    loop = [{"index": 2, "name": "Наушники HONOR [Loopback]", "is_loopback": True}]
    got = resolve_from_maps("Наушники", "loopback", mic, loop)
    assert got["is_loopback"] is True


def test_same_device_warning():
    a = {"index": 1, "name": "Same Device"}
    b = {"index": 1, "name": "Same Device"}
    assert same_device_warning(a, b) is not None
    c = {"index": 2, "name": "Other"}
    assert same_device_warning(a, c) is None
