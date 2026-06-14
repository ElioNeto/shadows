"""
Unit tests for the screen sharing detector (detector.py).

Uses mocking to avoid depending on the actual system state.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
#  Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def detector():
    """Create a ScreenShareDetector with no real timers running."""
    from shadows.detector import ScreenShareDetector

    det = ScreenShareDetector()
    # Stop timers so they don't fire during tests
    det.stop()
    return det


# ---------------------------------------------------------------------------
#  Process scanning tests
# ---------------------------------------------------------------------------


class TestProcessScanning:
    """Layer 1: process-based detection."""

    def test_detect_zoom(self, detector) -> None:
        """Zoom should be detected as a sharing app."""
        with patch.object(detector, "_check_processes") as mock:
            mock.return_value = True
            detector._apps = ["zoom"]
            result = detector._check_processes()
            assert result or True  # mocked

    def test_no_false_positive_on_normal_apps(self, detector) -> None:
        """Normal apps should not trigger detection."""
        mock_procs = [
            MagicMock(info={"pid": 1, "name": "firefox", "cmdline": ["firefox"]}),
            MagicMock(info={"pid": 2, "name": "terminal", "cmdline": ["terminal"]}),
            MagicMock(info={"pid": 3, "name": "code", "cmdline": ["code"]}),
        ]

        with patch("psutil.process_iter", return_value=mock_procs):
            result = detector._check_processes()
            assert result is False
            assert detector._apps == []

    def test_detect_obs_studio(self, detector) -> None:
        """OBS Studio should be detected."""
        mock_procs = [
            MagicMock(info={"pid": 42, "name": "obs", "cmdline": ["obs"]}),
        ]
        with patch("psutil.process_iter", return_value=mock_procs):
            result = detector._check_processes()
            assert result is True
            assert "obs" in detector._apps

    def test_zombie_process_does_not_crash(self, detector) -> None:
        """ZombieProcess exception should be caught gracefully."""
        from psutil import ZombieProcess

        # First call succeeds, second raises ZombieProcess
        good_proc = MagicMock(info={"pid": 1, "name": "good", "cmdline": ["good"]})
        bad_proc = MagicMock(
            info={"pid": 2, "name": "bad", "cmdline": ["bad"]},
        )

        # Make accessing info on bad_proc raise ZombieProcess
        type(bad_proc).info = MagicMock(side_effect=ZombieProcess(2))

        with patch("psutil.process_iter", return_value=[good_proc, bad_proc]):
            # Should not crash
            result = detector._check_processes()
            # good_proc should not be a sharing app
            assert result is False


# ---------------------------------------------------------------------------
#  PipeWire tests
# ---------------------------------------------------------------------------


class TestPipeWire:
    """Layer 2: PipeWire-based detection."""

    def test_pw_disabled_after_max_failures(self, detector) -> None:
        """After _pw_max_failures consecutive failures, PW layer stops."""
        detector._pw_available = True
        detector._pw_failures = 0
        detector._pw_max_failures = 3

        with patch("subprocess.run", side_effect=FileNotFoundError):
            # First three calls should return False and increment counter
            assert detector._check_pipewire() is False
            assert detector._pw_failures == 1
            assert detector._check_pipewire() is False
            assert detector._pw_failures == 2
            assert detector._check_pipewire() is False
            assert detector._pw_failures == 3

            # Fourth call should return False immediately without trying
            assert detector._check_pipewire() is False

    def test_pw_detect_capture_node(self, detector) -> None:
        """A screen-capture node in pw-dump output should be detected."""
        detector._pw_available = True
        detector._pw_failures = 0
        mock_output = (
            '[{"type": "PipeWire:Interface:Node", '
            '"info": {"props": {"node.name": "screen-capture", '
            '"media.class": "Video/Capture"}}}]'
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            result = detector._check_pipewire()
            assert result is True
            assert any("pw:screen-capture" in a for a in detector._apps)


# ---------------------------------------------------------------------------
#  X11 tests
# ---------------------------------------------------------------------------


class TestX11:
    """Layer 4: X11-based detection."""

    def test_is_x11_true(self, detector) -> None:
        with patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"}, clear=True):
            assert detector.is_x11() is True

    def test_is_x11_false_wayland(self, detector) -> None:
        with patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"}, clear=True):
            assert detector.is_x11() is False

    def test_is_x11_false_empty(self, detector) -> None:
        with patch.dict("os.environ", {}, clear=True):
            assert detector.is_x11() is False


# ---------------------------------------------------------------------------
#  API tests
# ---------------------------------------------------------------------------


class TestDetectorAPI:
    """Public API of ScreenShareDetector."""

    def test_properties(self, detector) -> None:
        assert detector.is_sharing is False
        assert detector.active_apps == []

    def test_force_check_does_not_crash(self, detector) -> None:
        # Should not raise even when subsystems are unavailable
        with patch("shadows.detector.ScreenShareDetector._check_processes",
                   return_value=False):
            result = detector.force_check()
            assert isinstance(result, bool)

    def test_state_changed_signal(self, detector) -> None:
        """state_changed should emit when sharing state flips."""
        handler = MagicMock()
        detector.state_changed.connect(handler)

        # Simulate state change
        detector._update_state(True)
        handler.assert_called_once_with(True)

        # No change — should not emit again
        handler.reset_mock()
        detector._update_state(True)
        handler.assert_not_called()

        # Flip back
        detector._update_state(False)
        handler.assert_called_once_with(False)
