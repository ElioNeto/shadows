"""
Multi-layer screen sharing detector for Linux (X11 + Wayland).

Detection layers (in order of speed / reliability):

  1. **Process scanning** (fastest, most portable) — checks for running
     processes belonging to known screen-sharing / recording applications
     (Zoom, Teams, OBS, Discord, OBS Studio, SimpleScreenRecorder, …).

  2. **PipeWire analysis** (Wayland-only) — parses ``pw-dump`` JSON output
     looking for active capture nodes whose ``media.class`` or
     ``node.name`` indicate screen / monitor capture.

  3. **DBus portal query** (Wayland + xdg-desktop-portal) — interrogates
     ``org.freedesktop.portal.ScreenCast`` for active session objects.

  4. **X11 atoms** (X11-only fallback) — reads the root window property
     ``_NET_WM_STATE`` looking for screen-recording indicators (limited).

Every layer emits a unified ``state_changed(is_sharing: bool)`` signal.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import subprocess
from collections.abc import Iterator
from enum import Enum
from typing import Optional

import psutil
from psutil import NoSuchProcess, AccessDenied, ZombieProcess
from PyQt5.QtCore import QObject, QTimer, pyqtSignal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known sharing / recording processes (lowercase)
# ---------------------------------------------------------------------------
SHARING_PROCESS_NAMES: set[str] = {
    # Video conferencing
    "zoom", "zoom-us", "teams", "ms-teams", "discord", "slack",
    "skype", "skypeforlinux", "webex", "bluejeans", "gotomeeting",
    "jitsi-meet", "whereby",
    # Remote desktop / remote support
    "anydesk", "teamviewer", "rustdesk", "splashtop", "todesk",
    "vnc", "vncviewer", "tigervnc", "realvnc", "x11vnc",
    "remmina", "rdesktop", "xfreerdp", "krfb", "krdc",
    # Screen recording
    "obs", "obs-studio", "obs64", "obs32",
    "simplescreenrecorder", "kazam", "peek", "kooha",
    "gnome-screen-recorder", "wl-screenrec", "gifine",
    "recordmydesktop", "byzanz", "green-recorder",
    # Streaming / capture tools
    "ffmpeg", "vlc", "mpv", "gstreamer",
    # NOT including "pipewire" — it is the system audio/video daemon
    # and is *always* running on Wayland; including it would cause
    # false positives on every modern Linux desktop.
}

# Browser processes — potential web-based sharing (Meet, Teams web, etc.)
BROWSER_PROCESSES: set[str] = {
    "chrome", "chromium", "chromium-browser", "firefox",
    "mozilla-firefox", "brave", "opera", "edge", "vivaldi",
}

# Media-class patterns that indicate screen capture in PipeWire.
# NOTE: "Video/Source" is intentionally excluded — it matches webcams
#       and other physical video inputs, not screen capture.
#       "Audio/Source" is also excluded (microphones).
PIPEWIRE_CAPTURE_CLASSES: set[str] = {
    "Screen/Capture",          # Direct screen capture
    "Video/Capture",           # Some compositors use this for screen cap
    "Stream/Capture",          # Streaming capture
}

# Additional media-class *substrings* that indicate capture intent
PIPEWIRE_CAPTURE_CLASS_SUBSTRINGS: list[str] = [
    "Screen/Capture",
    "screen-capture",
    "screencast",
]

# Regex patterns for PipeWire node names that indicate capture
PIPEWIRE_CAPTURE_PATTERNS: list[re.Pattern] = [
    re.compile(r".*screen.*capture.*", re.IGNORECASE),
    re.compile(r".*capture.*screen.*", re.IGNORECASE),
    re.compile(r".*screencast.*", re.IGNORECASE),
    re.compile(r".*screen.*cast.*", re.IGNORECASE),
    re.compile(r".*monitor.*capture.*", re.IGNORECASE),
    re.compile(r".*capture.*monitor.*", re.IGNORECASE),
    re.compile(r".*portal.*capture.*", re.IGNORECASE),
    re.compile(r".*wayfire.*screenshot.*", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Browser CLI flags that indicate media-capture intent (heuristic)
# ---------------------------------------------------------------------------
BROWSER_MEDIA_FLAGS: list[str] = [
    "--enable-features=mediacapture",
    "--disable-audio-capture",
    "screen-capture",
    "desktop-capture",
    "getdisplaymedia",
    "getusermedia",
    "chrome-extension://",  # screen-capture extensions
]


# ===================================================================
#  Detector
# ===================================================================
class ScreenShareDetector(QObject):
    """
    Polls multiple sources at configurable intervals and emits
    ``state_changed(is_sharing)`` whenever the sharing state flips.

    Parameters
    ----------
    process_interval_ms : int
        How often to scan running processes (default 2 s).
    pipewire_interval_ms : int
        How often to run ``pw-dump`` (default 5 s).  Ignored on X11.
    dbus_interval_ms : int
        How often to query the ScreenCast portal (default 5 s).
    """

    state_changed = pyqtSignal(bool, arguments=["is_sharing"])
    apps_changed = pyqtSignal(list, arguments=["apps"])

    def __init__(
        self,
        parent: Optional[QObject] = None,
        process_interval_ms: int = 2000,
        pipewire_interval_ms: int = 5000,
        dbus_interval_ms: int = 5000,
    ) -> None:
        super().__init__(parent)

        self._sharing: bool = False
        self._apps: list[str] = []

        # ── timers ────────────────────────────────────────────────
        self._process_timer = QTimer(self)
        self._process_timer.timeout.connect(self._check_processes)
        self._process_timer.setInterval(process_interval_ms)

        self._pw_timer = QTimer(self)
        self._pw_timer.timeout.connect(self._check_pipewire)
        self._pw_timer.setInterval(pipewire_interval_ms)

        self._dbus_timer = QTimer(self)
        self._dbus_timer.timeout.connect(self._check_dbus_portal)
        self._dbus_timer.setInterval(dbus_interval_ms)

        self._x11_timer = QTimer(self)
        self._x11_timer.timeout.connect(self._check_x11)
        self._x11_timer.setInterval(process_interval_ms)

        # Track whether each subsystem is usable (avoid repeated failures)
        self._pw_available: bool = self._probe_pipewire()
        self._pw_failures: int = 0
        self._pw_max_failures: int = 3
        self._dbus_available: bool = self._probe_dbus()

    # ── public API ────────────────────────────────────────────────
    @property
    def is_sharing(self) -> bool:
        """Whether screen sharing is currently detected."""
        return self._sharing

    @property
    def active_apps(self) -> list[str]:
        """Names of detected sharing applications."""
        return list(self._apps)

    def start(self) -> None:
        """Begin periodic monitoring."""
        self._process_timer.start()
        if self._pw_available:
            self._pw_timer.start()
        if self._dbus_available:
            self._dbus_timer.start()
        if self.is_x11():
            self._x11_timer.start()
        logger.info("ScreenShareDetector started (PW=%s DBus=%s X11=%s)",
                     self._pw_available, self._dbus_available, self.is_x11())

    def stop(self) -> None:
        """Stop periodic monitoring."""
        self._process_timer.stop()
        self._pw_timer.stop()
        self._dbus_timer.stop()
        self._x11_timer.stop()
        logger.info("ScreenShareDetector stopped")

    def force_check(self) -> bool:
        """Run all checks immediately and return current sharing state."""
        sharing = self._check_processes()
        if self._pw_available:
            sharing = self._check_pipewire() or sharing
        if self._dbus_available:
            sharing = self._check_dbus_portal() or sharing
        if self.is_x11():
            sharing = self._check_x11() or sharing
        self._update_state(sharing)
        return self._sharing

    # ── internal: state management ────────────────────────────────
    def _update_state(self, sharing: bool) -> None:
        if sharing != self._sharing:
            self._sharing = sharing
            self.state_changed.emit(sharing)
            self.apps_changed.emit(self._apps)
            logger.info("Share state changed → %s (apps=%s)",
                         "SHARING" if sharing else "CLEAR", self._apps)

    # ── Layer 1: process scanning ─────────────────────────────────
    def _check_processes(self) -> bool:
        """Scan running processes for known sharing applications."""
        apps: list[str] = []
        # ── fast name scan ────────────────────────────────────────
        running: dict[str, list] = {}
        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    name = (proc.info.get("name") or "").lower()
                    if name:
                        running.setdefault(name, []).append(proc.info)
                except (NoSuchProcess, AccessDenied, ZombieProcess):
                    continue
        except Exception as exc:
            logger.warning("Process scan error: %s", exc)
            return self._sharing

        # Check known sharing names
        found = running.keys() & SHARING_PROCESS_NAMES
        apps.extend(sorted(found))

        # Check browsers for media-capture CLI flags
        browsers = running.keys() & BROWSER_PROCESSES
        for browser in browsers:
            for pinfo in running[browser][:10]:
                cmd = " ".join(pinfo.get("cmdline") or [])
                if any(flag in cmd.lower() for flag in BROWSER_MEDIA_FLAGS):
                    apps.append(f"{browser} (capture)")
                    break  # one match per browser variant is enough

        changed = set(apps) != set(self._apps)
        self._apps = apps
        found_flag = bool(apps)

        if changed:
            self._update_state(found_flag)
            return found_flag

        # If no change, still propagate in case state was set by another layer
        if found_flag != self._sharing:
            self._update_state(found_flag)
        return found_flag

    # ── Layer 2: PipeWire analysis (Wayland) ──────────────────────
    def _probe_pipewire(self) -> bool:
        """Check whether ``pw-dump`` is available on this system."""
        try:
            subprocess.run(["pw-dump", "--version"],
                           capture_output=True, timeout=3)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _check_pipewire(self) -> bool:
        """Parse ``pw-dump`` output for screen-capture nodes.

        After ``_pw_max_failures`` consecutive failures the PipeWire
        layer is disabled for the remainder of the session to avoid
        spamming the logs.
        """
        if not self._pw_available:
            return False
        if self._pw_failures >= self._pw_max_failures:
            return False
        try:
            result = subprocess.run(
                ["pw-dump"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                self._pw_failures += 1
                return False
            # Robust JSON parsing: pw-dump may output multiple top-level
            # arrays/objects in some versions; wrap in list if needed.
            raw = result.stdout.strip()
            if not raw:
                self._pw_failures += 1
                return False
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                # Some PipeWire versions wrap results in an extra array
                # or use newline-delimited JSON; try line-by-line fallback.
                data = []
                for line in raw.splitlines():
                    line = line.strip()
                    if line:
                        try:
                            item = json.loads(line)
                            data.append(item)
                        except json.JSONDecodeError:
                            continue
                if not data:
                    self._pw_failures += 1
                    return False
        except (FileNotFoundError, json.JSONDecodeError,
                subprocess.TimeoutExpired, Exception) as exc:
            self._pw_failures += 1
            logger.debug("pw-dump failed (%d/%d): %s",
                         self._pw_failures, self._pw_max_failures, exc)
            if self._pw_failures >= self._pw_max_failures:
                logger.warning("PipeWire layer disabled after %d failures",
                               self._pw_failures)
            return False

        # Normalize data to a list of entries (handle both array and object wrappers)
        if isinstance(data, dict):
            data = [data]
        elif not isinstance(data, list):
            self._pw_failures += 1
            return False

        capture_nodes: list[str] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            if entry.get("type") not in ("PipeWire:Interface:Node", "Node"):
                continue
            # Navigate safely through potentially missing keys
            info = entry.get("info")
            if not isinstance(info, dict):
                continue
            props = info.get("props")
            if not isinstance(props, dict):
                continue
            name: str = str(props.get("node.name", "") or "")
            media_class: str = str(props.get("media.class", "") or "")

            # Check media.class — exact match
            if media_class in PIPEWIRE_CAPTURE_CLASSES:
                capture_nodes.append(name or media_class)
                continue

            # Check media.class — substring match
            if any(sub in media_class for sub in PIPEWIRE_CAPTURE_CLASS_SUBSTRINGS):
                capture_nodes.append(name or media_class)
                continue

            # Check node name patterns
            for pat in PIPEWIRE_CAPTURE_PATTERNS:
                if pat.match(name):
                    capture_nodes.append(name)
                    break

        # Reset failure counter on success
        self._pw_failures = 0

        if capture_nodes:
            for node in capture_nodes:
                if f"pw:{node}" not in self._apps:
                    self._apps.append(f"pw:{node}")
            self._update_state(True)
            return True

        # Clean stale PipeWire entries from app list
        stale = [a for a in self._apps if a.startswith("pw:")]
        if stale:
            self._apps = [a for a in self._apps if not a.startswith("pw:")]
            # Re-evaluate overall state
            self._update_state(bool(self._apps))
        return bool(capture_nodes)

    # ── Layer 3: DBus portal query ────────────────────────────────
    def _probe_dbus(self) -> bool:
        """Check whether the ScreenCast portal is reachable via DBus."""
        try:
            import dbus  # type: ignore[import-untyped]
            bus = dbus.SessionBus()
            obj = bus.get_object(
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
            )
            obj.Introspect(dbus_interface="org.freedesktop.DBus.Introspectable")
            return True
        except Exception:
            return False

    def _check_dbus_portal(self) -> bool:
        """
        Attempt to detect active ScreenCast sessions via DBus.

        Uses ``busctl`` to list objects under the portal's object path
        and checks for session-related sub-paths — a lightweight
        alternative to subscribing to portal signals.
        """
        if not self._dbus_available:
            return False
        try:
            result = subprocess.run(
                ["busctl", "tree", "org.freedesktop.portal.Desktop"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return False
            # Session paths typically look like:
            #   /org/freedesktop/portal/desktop/session/...
            session_paths = [
                line.strip()
                for line in result.stdout.splitlines()
                if "/session/" in line
            ]
            if session_paths and not self._sharing:
                logger.debug("Active portal sessions: %d", len(session_paths))
                self._apps.append("dbus:portal-screen-cast")
                self._update_state(True)
                return True
            elif not session_paths:
                # Clean stale DBus entries
                stale = [a for a in self._apps if a.startswith("dbus:")]
                if stale:
                    self._apps = [a for a in self._apps
                                  if not a.startswith("dbus:")]
                    self._update_state(bool(self._apps))
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as exc:
            logger.debug("DBus portal check failed: %s", exc)
        return self._sharing

    # ── Layer 4: X11 atoms (legacy fallback) ──────────────────────
    @staticmethod
    def is_x11() -> bool:
        """Return True if running under X11 (not Wayland)."""
        return os.environ.get("XDG_SESSION_TYPE", "").lower() == "x11"

    def _check_x11(self) -> bool:
        """
        Detect screen sharing / recording on X11 by inspecting
        ``_NET_WM_STATE`` and ``_NET_CLIENT_LIST``.

        Uses ``xprop`` and ``xdotool`` as lightweight CLI tools that are
        almost always available on X11 desktops.
        """
        if not self.is_x11():
            return False

        sharing_found = False
        try:
            # Get list of all windows
            result = subprocess.run(
                ["xdotool", "search", "--onlyvisible", "--name", ".*"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return False

            window_ids = result.stdout.strip().split()
            # Known WM_CLASS strings for screen-sharing tools
            x11_sharing_classes = {
                "zoom", "teams", "obs", "obs-studio",
                "simplescreenrecorder", "kazam", "peek",
            }
            for wid in window_ids[:50]:  # limit to first 50 windows
                try:
                    cls_result = subprocess.run(
                        ["xprop", "-id", wid, "WM_CLASS"],
                        capture_output=True, text=True, timeout=2,
                    )
                    if cls_result.returncode != 0:
                        continue
                    # WM_CLASS(STRING) = "firefox", "Firefox"
                    cls_text = cls_result.stdout.strip().lower()
                    for cls_name in x11_sharing_classes:
                        if cls_name in cls_text:
                            app_name = f"x11:{cls_name}"
                            if app_name not in self._apps:
                                self._apps.append(app_name)
                            sharing_found = True
                            break
                except (subprocess.TimeoutExpired, OSError):
                    continue

            if sharing_found:
                self._update_state(True)
                return True

        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            logger.debug("X11 check failed: %s", exc)

        # Clean stale X11 entries
        stale = [a for a in self._apps if a.startswith("x11:")]
        if stale:
            self._apps = [a for a in self._apps if not a.startswith("x11:")]
            self._update_state(bool(self._apps))
        return sharing_found


# ===================================================================
#  Convenience helper
# ===================================================================
def quick_detect() -> tuple[bool, list[str]]:
    """
    Run a one-shot detection scan and return ``(is_sharing, app_names)``.
    Useful for CLI scripts or quick checks without starting a full event loop.
    """
    detector = ScreenShareDetector()
    sharing = detector.force_check()
    return sharing, detector.active_apps
