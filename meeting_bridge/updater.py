"""Check GitHub Releases and launch the latest Windows installer."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

from meeting_bridge.version import __version__

LATEST_RELEASE_API = (
    "https://api.github.com/repos/Aleksey341/1C_Analitik/releases/latest"
)
ASSET_NAME = "1C-Analitik-Setup.exe"
USER_AGENT = "1C-Analitik-Updater"


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag: str
    download_url: str
    digest: str = ""


def _version_tuple(value: str) -> tuple[int, ...]:
    clean = value.strip().lower().lstrip("v")
    numbers: list[int] = []
    for part in clean.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        if not digits:
            break
        numbers.append(int(digits))
    return tuple(numbers or [0])


def is_newer(candidate: str, current: str = __version__) -> bool:
    return _version_tuple(candidate) > _version_tuple(current)


def fetch_latest_release(timeout: float = 4.0) -> ReleaseInfo | None:
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None

    tag = str(payload.get("tag_name") or "").strip()
    version = tag.lstrip("v")
    if not tag or not version:
        return None

    for asset in payload.get("assets") or []:
        if str(asset.get("name") or "") != ASSET_NAME:
            continue
        url = str(asset.get("browser_download_url") or "").strip()
        if not url:
            continue
        return ReleaseInfo(
            version=version,
            tag=tag,
            download_url=url,
            digest=str(asset.get("digest") or "").strip(),
        )
    return None


def download_installer(release: ReleaseInfo, timeout: float = 90.0) -> Path:
    destination = Path(tempfile.gettempdir()) / (
        f"1C-Analitik-Setup-{release.version}.exe"
    )
    request = urllib.request.Request(
        release.download_url,
        headers={"User-Agent": USER_AGENT},
    )
    sha256 = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        with destination.open("wb") as target:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                target.write(chunk)
                sha256.update(chunk)

    digest = release.digest.casefold()
    if digest.startswith("sha256:"):
        expected = digest.split(":", 1)[1].strip()
        actual = sha256.hexdigest().casefold()
        if expected and actual != expected:
            try:
                destination.unlink()
            except OSError:
                pass
            raise RuntimeError(
                "Контрольная сумма обновления не совпала. Загрузка отменена."
            )
    return destination


def launch_installer(path: Path) -> None:
    subprocess.Popen(
        [
            str(path),
            "/SILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            "/CLOSEAPPLICATIONS",
        ],
        close_fds=True,
    )


def maybe_offer_update() -> bool:
    """Offer the latest release before the main GUI opens.

    Returns True only when an installer was launched and the current process
    should exit so Inno Setup can replace the installed files.
    """
    if not getattr(sys, "frozen", False):
        return False

    release = fetch_latest_release()
    if release is None or not is_newer(release.version):
        return False

    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    try:
        accepted = messagebox.askyesno(
            "Обновление 1С Аналитик",
            f"Доступна новая версия {release.version}.\n"
            f"Установленная версия: {__version__}.\n\n"
            "Обновить сейчас?",
            parent=root,
        )
        if not accepted:
            return False

        try:
            installer = download_installer(release)
            launch_installer(installer)
        except Exception as exc:  # noqa: BLE001
            messagebox.showwarning(
                "Обновление 1С Аналитик",
                "Не удалось автоматически скачать обновление.\n\n"
                f"{exc}\n\n"
                "Программа продолжит работу в текущей версии.",
                parent=root,
            )
            return False

        messagebox.showinfo(
            "Обновление 1С Аналитик",
            "Обновление скачано. Сейчас запустится установщик, "
            "а текущая версия приложения закроется.",
            parent=root,
        )
        return True
    finally:
        root.destroy()
