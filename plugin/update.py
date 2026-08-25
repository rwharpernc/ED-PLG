"""
Self-update: checks GitHub Releases for a newer ED-PLG build, downloads it,
and stages it over the current install. Staged files only take effect on
EDMC's next restart - nothing here reloads running code.

Runs in a background thread (network I/O) and never touches Tkinter
directly - it hands the new version string to a plain callback, which the
caller (load.py) marshals onto the main thread via a frame.after(0, ...)
call in ui.py. This is ED-PLG's one exception to being pure stdlib+EDMC -
see README's "Auto-update" section.

Uses only the standard library (urllib, zipfile) rather than a pip
package, to keep "no pip dependencies" true (see docs/tech-spec.md §12)
even though the plugin makes one network call now.

Deliberately independent of ui.py's config reads (whether auto-update is
enabled is passed into check_async() by the caller) so this module has no
Tkinter/myNotebook dependency of its own.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from zipfile import ZipFile

from config import appname, config

from . import __version__

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

_GITHUB_REPO = "rwharpernc/ED-PLG"
"""The GitHub repo slug - distinct from the installed folder name (EDPLG,
no hyphen - see scripts/package.mjs), which is only used below for local
file naming, never for these URLs."""

RELEASES_API_URL = f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest"
RELEASES_PAGE_URL = f"https://github.com/{_GITHUB_REPO}/releases/latest"
REQUEST_TIMEOUT_S = 15
DOWNLOAD_TIMEOUT_S = 60
_USER_AGENT = "ED-PLG-auto-update"

CONFIG_AUTO_UPDATE = "edplg_auto_update"
CONFIG_LAST_VERSION = "edplg_last_version"
"""Not a user preference (see CONFIG_AUTO_UPDATE for that) - purely
internal bookkeeping for check_applied_update() to detect a staged update
having just taken effect."""

UPDATES_DIRNAME = "updates"
BACKUPS_DIRNAME = "backups"
BACKUPS_KEEP = 3
# Dev handbrake: drop a file with this name in the plugin folder to disable
# auto-update for that install, regardless of the Settings checkbox - e.g.
# for a folder you're actively hand-editing/testing builds in.
DISABLE_SENTINEL = "disable-auto-update.txt"

# Never touched by backup, even though they live inside plugin_dir - none
# of these ship in a release zip (see scripts/build.mjs), so _apply()
# never touches them either.
_OWN_DIRS = {UPDATES_DIRNAME, BACKUPS_DIRNAME, "__pycache__"}


def _parse_version(value: str) -> Optional[tuple[int, ...]]:
    try:
        parts = tuple(int(p) for p in value.strip().lstrip("vV").split("."))
    except ValueError:
        return None
    return parts if parts else None


def _pad(a: tuple[int, ...], b: tuple[int, ...]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    length = max(len(a), len(b))
    return a + (0,) * (length - len(a)), b + (0,) * (length - len(b))


def current_version() -> str:
    return __version__


def check_applied_update() -> Optional[str]:
    """Compares the running version against the version recorded on the
    previous run and records the current one for next time.

    Returns the current version string if it differs from what was
    previously recorded (i.e. a staged update just took effect on this
    restart), or None on the first-ever run or when nothing changed.
    """
    previous = config.get_str(CONFIG_LAST_VERSION)
    config.set(CONFIG_LAST_VERSION, __version__)
    if previous and previous != __version__:
        return __version__
    return None


class UpdateManager:
    """Checks once, downloads/stages at most once, per EDMC run."""

    def __init__(
        self,
        plugin_dir: str,
        on_ready: Callable[[str], None],
        on_downloading: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._plugin_dir = plugin_dir
        self._plugin_name = Path(plugin_dir).name  # "EDPLG" for a normal install
        self._updates_dir = os.path.join(plugin_dir, UPDATES_DIRNAME)
        self._backups_dir = os.path.join(plugin_dir, BACKUPS_DIRNAME)
        self._on_ready = on_ready
        self._on_downloading = on_downloading

    def check_async(self) -> None:
        if os.path.exists(os.path.join(self._plugin_dir, DISABLE_SENTINEL)):
            logger.info(f"Auto-update disabled by {DISABLE_SENTINEL}")
            return
        if not config.get_bool(CONFIG_AUTO_UPDATE, default=False):
            logger.info("Auto-update disabled in Settings")
            return
        threading.Thread(target=self._check, name="ED-PLG-update-check", daemon=True).start()

    def _check(self) -> None:
        current = _parse_version(__version__)
        if current is None:
            logger.warning(f"Could not parse current version {__version__!r}; skipping update check")
            return

        try:
            request = urllib.request.Request(
                RELEASES_API_URL,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/vnd.github+json"},
            )
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception:
            logger.debug("Update check failed", exc_info=True)
            return

        if data.get("draft") or data.get("prerelease"):
            return

        remote = _parse_version(str(data.get("tag_name", "")))
        if remote is None:
            logger.debug(f"Could not parse remote version {data.get('tag_name')!r}")
            return

        current_p, remote_p = _pad(current, remote)
        if remote_p <= current_p:
            logger.info(f"ED-PLG up to date (v{__version__})")
            return

        remote_str = ".".join(str(p) for p in remote)
        assets = data.get("assets") or []
        download_url = next(
            (a.get("browser_download_url") for a in assets if str(a.get("name", "")).endswith(".zip")),
            None,
        )
        if not download_url:
            logger.warning(f"Release v{remote_str} has no .zip asset to download")
            return

        logger.info(f"Downloading ED-PLG v{remote_str} (current: v{__version__})")
        self._download_and_stage(download_url, remote_str)

    def _download_and_stage(self, url: str, version: str) -> None:
        os.makedirs(self._updates_dir, exist_ok=True)
        zip_path = os.path.join(self._updates_dir, f"{self._plugin_name}-v{version}.zip")

        if self._on_downloading is not None:
            self._on_downloading(version)

        try:
            request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_S) as response, \
                    open(zip_path, "wb") as fh:
                shutil.copyfileobj(response, fh)
        except Exception:
            logger.warning(f"Failed to download v{version} update", exc_info=True)
            return

        try:
            self._backup_current()
            self._apply(zip_path)
        except Exception:
            logger.warning(f"Failed to stage v{version} update", exc_info=True)
            return

        logger.info(f"ED-PLG v{version} staged - restart EDMC to apply")
        self._on_ready(version)

    def _backup_current(self) -> None:
        os.makedirs(self._backups_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = os.path.join(self._backups_dir, f"{stamp}.zip")

        with ZipFile(backup_path, "w") as zf:
            for root, dirs, files in os.walk(self._plugin_dir):
                dirs[:] = [d for d in dirs if d not in _OWN_DIRS]
                for name in files:
                    if name.endswith((".pyc", ".pyo")):
                        continue
                    full = os.path.join(root, name)
                    zf.write(full, os.path.relpath(full, self._plugin_dir))

        self._trim_backups()

    def _trim_backups(self) -> None:
        backups = sorted(
            (os.path.join(self._backups_dir, f) for f in os.listdir(self._backups_dir)),
            key=os.path.getctime,
        )
        for stale in backups[:-BACKUPS_KEEP]:
            try:
                os.remove(stale)
            except OSError:
                logger.debug(f"Could not remove stale backup {stale}", exc_info=True)

    def _apply(self, zip_path: str) -> None:
        with ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            # Release zips contain a top-level EDPLG/ folder (see
            # scripts/package.mjs), so strip it - plugin_dir *is* that
            # folder already.
            prefix = names[0].split("/", 1)[0] + "/" if names and "/" in names[0] else ""

            for member in zf.infolist():
                relative = member.filename[len(prefix):] \
                    if prefix and member.filename.startswith(prefix) else member.filename
                if not relative:
                    continue

                target = os.path.join(self._plugin_dir, relative)
                if member.is_dir():
                    os.makedirs(target, exist_ok=True)
                    continue

                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
