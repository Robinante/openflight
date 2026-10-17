"""Readiness follows capture workers without issuing hardware commands."""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from openflight import server
from openflight.iwr6843.monitor import IWR6843CaptureMonitor
from openflight.rolling_buffer.monitor import RollingBufferMonitor


@pytest.mark.parametrize("state", ["waiting", "capturing", "processing", "error"])
def test_ops_reports_worker_state_and_rearm_failure(state):
    monitor = RollingBufferMonitor(trigger_type="hardware")
    monitor._running = True
    monitor._capture_thread = MagicMock()
    monitor._capture_state = state
    assert monitor.capture_status() == state
    monitor.trigger.rearm_pending = True
    assert monitor.capture_status() == "recovering"
    monitor._capture_thread.is_alive.return_value = False
    assert monitor.capture_status() == "unavailable"


@pytest.mark.parametrize(
    ("flag", "expected"),
    [
        ("_capture_active", "capturing"),
        ("_edge_pending", "capturing"),
        ("_rearming", "recovering"),
        ("_release_pending", "recovering"),
        ("_job_active", "processing"),
        ("_listener_error", "error"),
    ],
)
def test_iwr_reports_busy_work_without_querying_the_serial_port(tmp_path, flag, expected):
    radar = MagicMock()
    monitor = IWR6843CaptureMonitor(
        config_path=tmp_path / "unused.cfg", output_dir=tmp_path, radar=radar
    )
    monitor._running = True
    monitor._armed = True
    monitor._worker = MagicMock()
    assert monitor.capture_status() == "waiting"
    setattr(monitor, flag, True)
    assert monitor.capture_status() == expected
    radar.stats.assert_not_called()


def test_capture_endpoint_never_calls_ready_with_a_busy_or_missing_device(monkeypatch):
    ops = SimpleNamespace(capture_status=lambda: "waiting")
    iwr = SimpleNamespace(capture_status=lambda: "capturing", save_dumps=True)
    monkeypatch.setattr(server, "mock_mode", False)
    monkeypatch.setattr(server, "monitor", ops)
    monkeypatch.setattr(server, "iwr6843_runtime", SimpleNamespace(capture_monitor=iwr))
    monkeypatch.setattr(server, "iwr6843_runtime_config", {"enabled": True})
    monkeypatch.setattr(server, "camera_capture_runtime", None)
    monkeypatch.setattr(server, "camera_capture_config", {"enabled": False})
    client = server.app.test_client()
    reply = client.get("/api/capture-status")
    assert reply.status_code == 200
    assert reply.json == {
        "ready": False,
        "devices": {"OPS": "waiting", "IWR": "capturing"},
        "raw_iwr": True,
        "mock": False,
    }
    iwr.capture_status = lambda: "waiting"
    assert client.get("/api/capture-status").json["ready"] is True
    monkeypatch.setattr(server, "iwr6843_runtime", None)
    assert client.get("/api/capture-status").json["ready"] is False


def test_hardware_trigger_forwards_shutdown_and_first_byte_callback():
    from openflight.rolling_buffer.trigger import HardwareTriggeredCapture

    radar = MagicMock()
    radar.wait_for_hardware_trigger.return_value = ""
    cancel = threading.Event()
    callback = MagicMock()
    HardwareTriggeredCapture().wait_for_trigger(
        radar, MagicMock(), cancel_event=cancel, capture_started_callback=callback
    )
    assert radar.wait_for_hardware_trigger.call_args.kwargs["cancel_event"] is cancel
    assert radar.wait_for_hardware_trigger.call_args.kwargs["on_first_byte"] is callback
