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


def _entry(info: DeviceInfo, *, force_loopback: bool | None = None) -> DeviceInfo | None:
    name = str(info.get("name", "")).strip()
    max_in = int(info.get("maxInputChannels", 0) or 0)
    if not name or max_in <= 0:
        return None
    is_loop = (
        bool(force_loopback)
        if force_loopback is not None
        else bool(info.get("isLoopbackDevice", False)) or "loopback" in name.casefold()
    )
    return {
        "index": int(info.get("index", -1)),
        "name": name,
        "hostapi": info.get("hostApi"),
        "is_loopback": is_loop,
        "defaultSampleRate": info.get("defaultSampleRate"),
        "maxInputChannels": max_in,
        "is_default": bool(info.get("is_default", False)),
    }


def _append_unique(target: list[DeviceInfo], item: DeviceInfo | None) -> None:
    if item is None:
        return
    index = item.get("index")
    name = str(item.get("name", "")).casefold()
    for existing in target:
        if existing.get("index") == index or str(existing.get("name", "")).casefold() == name:
            if item.get("is_default"):
                existing["is_default"] = True
            return
    target.append(item)


def _collect_audio_devices(p, pyaudio_module) -> dict[str, list[DeviceInfo]]:  # noqa: ANN001
    """Collect capture devices, preferring PyAudioWPatch's dedicated WASAPI APIs.

    PyAudioWPatch exposes output loopback devices as virtual input devices.  On
    some Windows/audio-driver combinations these devices are more reliably
    returned by get_loopback_device_info_generator() than by a plain device
    enumeration, so use that API first and keep enumeration as a fallback.
    """
    mic: list[DeviceInfo] = []
    loopback: list[DeviceInfo] = []

    wasapi_index: int | None = None
    try:
        wasapi = p.get_host_api_info_by_type(pyaudio_module.paWASAPI)
        wasapi_index = int(wasapi.get("index", -1))
        if wasapi_index < 0:
            # Some PyAudio builds omit the explicit index in the returned dict.
            default_out = wasapi.get("defaultOutputDevice")
            for api_index in range(p.get_host_api_count()):
                api = p.get_host_api_info_by_index(api_index)
                if "wasapi" in str(api.get("name", "")).casefold():
                    wasapi_index = api_index
                    break
            if wasapi_index is not None and wasapi_index < 0 and default_out is None:
                wasapi_index = None
    except (AttributeError, OSError, TypeError, ValueError):
        # Keep a name-based fallback for older/driver-specific PyAudio builds.
        try:
            for api_index in range(p.get_host_api_count()):
                api = p.get_host_api_info_by_index(api_index)
                if "wasapi" in str(api.get("name", "")).casefold():
                    wasapi_index = api_index
                    break
        except Exception:  # noqa: BLE001
            wasapi_index = None

    all_infos: list[DeviceInfo] = []
    for i in range(p.get_device_count()):
        info = dict(p.get_device_info_by_index(i))
        info.setdefault("index", i)
        all_infos.append(info)

    # Microphones: prefer WASAPI input devices. If a driver exposes no WASAPI
    # microphone, retain normal input devices as a fallback.
    wasapi_mics: list[DeviceInfo] = []
    fallback_mics: list[DeviceInfo] = []
    for info in all_infos:
        item = _entry(info)
        if item is None or item["is_loopback"]:
            continue
        if wasapi_index is not None and int(info.get("hostApi", -1)) == wasapi_index:
            _append_unique(wasapi_mics, item)
        else:
            _append_unique(fallback_mics, item)
    mic.extend(wasapi_mics or fallback_mics)

    # Loopback: this is the canonical PyAudioWPatch path and also works with
    # Bluetooth headphones supported by WASAPI.
    try:
        for raw in p.get_loopback_device_info_generator():
            info = dict(raw)
            item = _entry(info, force_loopback=True)
            _append_unique(loopback, item)
    except (AttributeError, OSError, LookupError):
        pass

    # Identify the current Windows default output loopback and put it first. This
    # makes hot-plugged headphones the automatic choice when Windows switched the
    # default playback device to them.
    default_loop: DeviceInfo | None = None
    try:
        raw_default = dict(p.get_default_wasapi_loopback())
        raw_default["is_default"] = True
        default_loop = _entry(raw_default, force_loopback=True)
        _append_unique(loopback, default_loop)
    except (AttributeError, OSError, LookupError, TypeError):
        default_loop = None

    # Fallback for package/driver versions where the dedicated generator is not
    # available but the duplicated loopback device is visible in enumeration.
    if not loopback:
        for info in all_infos:
            is_loop = bool(info.get("isLoopbackDevice", False)) or "loopback" in str(info.get("name", "")).casefold()
            if not is_loop:
                continue
            _append_unique(loopback, _entry(info, force_loopback=True))

    if default_loop is not None:
        default_index = default_loop.get("index")
        default_name = str(default_loop.get("name", "")).casefold()
        for item in loopback:
            if item.get("index") == default_index or str(item.get("name", "")).casefold() == default_name:
                item["is_default"] = True
        loopback.sort(key=lambda item: (not bool(item.get("is_default")), str(item.get("name", "")).casefold()))

    return {"mic": mic, "loopback": loopback}


def list_audio_devices() -> dict[str, list[DeviceInfo]]:
    import pyaudiowpatch as pyaudio  # type: ignore

    p = pyaudio.PyAudio()
    try:
        return _collect_audio_devices(p, pyaudio)
    finally:
        p.terminate()


def resolve_device(name_substring: str, kind: Literal["mic", "loopback"]) -> DeviceInfo:
    maps = list_audio_devices()
    return resolve_from_maps(name_substring, kind, maps["mic"], maps["loopback"])
