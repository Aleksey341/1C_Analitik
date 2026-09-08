from __future__ import annotations

from typing import Any, Literal

DeviceInfo = dict[str, Any]


def same_device_warning(mic: DeviceInfo, loopback: DeviceInfo) -> str | None:
    if mic.get("index") == loopback.get("index") or mic.get("name") == loopback.get("name"):
        return (
            "Микрофон и собеседник указывают на одно устройство. "
            "Для собеседника выберите loopback наушников/динамиков."
        )
    return None


def resolve_from_maps(
    name_substring: str,
    kind: Literal["mic", "loopback"],
    mic: list[DeviceInfo],
    loopback: list[DeviceInfo],
) -> DeviceInfo:
    pool = mic if kind == "mic" else loopback
    needle = name_substring.casefold()
    for d in pool:
        if needle in str(d.get("name", "")).casefold():
            return d
    raise LookupError(f"No {kind} device matching {name_substring!r}")


def list_audio_devices() -> dict[str, list[DeviceInfo]]:
    import pyaudiowpatch as pyaudio  # type: ignore

    mic: list[DeviceInfo] = []
    loopback: list[DeviceInfo] = []
    p = pyaudio.PyAudio()
    try:
        wasapi_index = None
        for api_index in range(p.get_host_api_count()):
            api = p.get_host_api_info_by_index(api_index)
            if "wasapi" in str(api.get("name", "")).casefold():
                wasapi_index = api_index
                break

        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            # Prefer WASAPI: full device names + real loopback support.
            if wasapi_index is not None and int(info.get("hostApi", -1)) != wasapi_index:
                continue
            name = str(info.get("name", "")).strip()
            max_in = int(info.get("maxInputChannels", 0))
            is_loop = bool(info.get("isLoopbackDevice", False)) or ("loopback" in name.casefold())
            if max_in <= 0:
                continue
            entry = {
                "index": i,
                "name": name,
                "hostapi": info.get("hostApi"),
                "is_loopback": is_loop,
                "defaultSampleRate": info.get("defaultSampleRate"),
                "maxInputChannels": max_in,
            }
            if is_loop:
                loopback.append(entry)
            else:
                mic.append(entry)
    finally:
        p.terminate()
    return {"mic": mic, "loopback": loopback}


def resolve_device(name_substring: str, kind: Literal["mic", "loopback"]) -> DeviceInfo:
    maps = list_audio_devices()
    return resolve_from_maps(name_substring, kind, maps["mic"], maps["loopback"])
