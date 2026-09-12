from meeting_bridge.devices import _collect_audio_devices, resolve_from_maps, same_device_warning


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


class _AudioModule:
    paWASAPI = 13


class _FakeAudio:
    def __init__(self):
        self.devices = [
            {
                "index": 0,
                "name": "Микрофон Realtek",
                "hostApi": 2,
                "maxInputChannels": 2,
                "defaultSampleRate": 48000,
                "isLoopbackDevice": False,
            },
            {
                "index": 1,
                "name": "Headphones Bluetooth",
                "hostApi": 2,
                "maxInputChannels": 0,
                "defaultSampleRate": 48000,
                "isLoopbackDevice": False,
            },
        ]
        self.loops = [
            {
                "index": 7,
                "name": "Headphones Bluetooth [Loopback]",
                "hostApi": 2,
                "maxInputChannels": 2,
                "defaultSampleRate": 48000,
                "isLoopbackDevice": True,
            },
            {
                "index": 8,
                "name": "Speakers Realtek [Loopback]",
                "hostApi": 2,
                "maxInputChannels": 2,
                "defaultSampleRate": 48000,
                "isLoopbackDevice": True,
            },
        ]

    def get_host_api_info_by_type(self, _kind):
        return {"index": 2, "name": "Windows WASAPI", "defaultOutputDevice": 1}

    def get_host_api_count(self):
        return 3

    def get_host_api_info_by_index(self, index):
        return {"name": "Windows WASAPI" if index == 2 else "Other"}

    def get_device_count(self):
        return len(self.devices)

    def get_device_info_by_index(self, index):
        return self.devices[index]

    def get_loopback_device_info_generator(self):
        yield from self.loops

    def get_default_wasapi_loopback(self):
        return self.loops[0]


def test_dedicated_loopback_generator_finds_bluetooth_headphones():
    result = _collect_audio_devices(_FakeAudio(), _AudioModule)
    assert result["mic"][0]["name"] == "Микрофон Realtek"
    assert result["loopback"][0]["name"] == "Headphones Bluetooth [Loopback]"
    assert result["loopback"][0]["is_default"] is True


class _DefaultOnlyAudio(_FakeAudio):
    def get_loopback_device_info_generator(self):
        raise AttributeError("generator unavailable")


def test_default_wasapi_loopback_is_used_when_generator_unavailable():
    result = _collect_audio_devices(_DefaultOnlyAudio(), _AudioModule)
    assert len(result["loopback"]) == 1
    assert result["loopback"][0]["name"] == "Headphones Bluetooth [Loopback]"
    assert result["loopback"][0]["is_default"] is True
