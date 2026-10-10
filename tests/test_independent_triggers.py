"""Bench experiment: autonomous OPS and IWR capture paths (no real hardware)."""

import sys
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from iwr6843_fakes import FakeIWRRuntime

from openflight import server
from openflight.rolling_buffer import trigger as triggers
from openflight.rolling_buffer.types import IQCapture, SpeedReading, SpeedTimeline


@pytest.fixture(autouse=True)
def restore_server_settings(monkeypatch):
    for name in (
        "mock_mode",
        "mock_swing_speed_mode",
        "debug_mode",
        "radar_config",
        "ballistics_enabled",
        "battery_provider",
        "profile_store",
        "ball_speed_correction_enabled",
        "ball_speed_correction_distance_ft",
        "ball_speed_correction_ball_above_radar_ft",
        "_VERTICAL_RADAR_GATE_BYPASS",
        "calculated_spin_enabled",
        "flight_environment",
        "ble_publisher",
        "sim_connectors",
    ):
        monkeypatch.setattr(server, name, getattr(server, name))


@pytest.mark.parametrize("trigger_type", ["hardware", "sound"])
def test_iwr_only_sends_s_bang_in_sound_mode(monkeypatch, trigger_type):
    monitor = MagicMock()
    monitor.get_radar_info.return_value = {"Version": "1.3.2"}
    capture_monitor = MagicMock(watch_self_trigger=True)
    session = MagicMock()
    monkeypatch.setattr(server, "monitor", None)
    monkeypatch.setattr(server, "inclinometer_service", None)
    monkeypatch.setattr(server, "get_session_logger", lambda: session)
    monkeypatch.setattr(server, "iwr6843_runtime", SimpleNamespace(capture_monitor=capture_monitor))
    monkeypatch.setattr("openflight.rolling_buffer.RollingBufferMonitor", lambda **kwargs: monitor)

    server.start_monitor(trigger_type=trigger_type)

    capture_monitor.arm.assert_called_once()
    if trigger_type == "sound":
        observer = capture_monitor.add_trigger_observer.call_args.args[0]
        observer(100.0)
        monitor.radar.request_capture.assert_called_once_with()
        monitor.radar.read_clock_sync.assert_called_once()
    else:
        capture_monitor.add_trigger_observer.assert_not_called()
        monitor.radar.request_capture.assert_not_called()
        monitor.radar.read_clock_sync.assert_not_called()


def test_cli_accepts_both_autonomous_triggers(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "openflight-server",
            "--no-logging",
            "--trigger",
            "hardware",
            "--iwr6843",
            "--iwr6843-self-trigger",
        ],
    )
    monkeypatch.setattr(server, "start_monitor", start)
    monkeypatch.setattr(server, "init_iwr6843", lambda **kwargs: True)
    runtime = FakeIWRRuntime()
    runtime.tx_order = "012"
    monkeypatch.setattr(server, "iwr6843_runtime", runtime)
    monkeypatch.setattr(server, "load_sim_config", lambda: [])
    monkeypatch.setattr(server, "build_connectors", lambda *args, **kwargs: [])
    monkeypatch.setattr(server, "init_session_logger", lambda **kwargs: None)
    monkeypatch.setattr(server, "_cleanup_hardware_for_shutdown", lambda: None)
    monkeypatch.setattr(server.socketio, "run", lambda *args, **kwargs: None)
    server.main()
    assert start.call_args.kwargs["trigger_type"] == "hardware"


def test_independent_capture_does_not_report_s_bang_latency(monkeypatch, caplog):
    monkeypatch.setattr(server, "iwr6843_runtime", SimpleNamespace(self_trigger_enabled=True))
    monkeypatch.setattr(server, "monitor", SimpleNamespace(trigger_type="hardware"))
    with caplog.at_level("INFO"):
        server._check_self_trigger_latency(
            SimpleNamespace(impact_timestamp=100.0), SimpleNamespace(trigger_timestamp=100.080)
        )
    assert "impact -> S!" not in caplog.text
    assert "80.0 ms" in caplog.text


def test_ops_information_is_read_before_arming():
    from openflight.rolling_buffer import RollingBufferMonitor

    monitor = RollingBufferMonitor(trigger_type="hardware")
    monitor.radar = MagicMock()
    monitor.radar.get_info.return_value = {"Version": "1.3.2"}
    monitor.connect()
    names = [call[0] for call in monitor.radar.mock_calls]
    assert names.index("get_info") < names.index("configure_for_internal_speed_trigger")
    monitor.radar.reset_mock()
    assert monitor.get_radar_info()["Version"] == "1.3.2"
    monitor.radar.get_info.assert_not_called()


@pytest.mark.parametrize("clock_mode", ["fresh", "previous", "stale", "error"])
def test_ops_clock_mapping_precedes_rearm_and_preserves_fallback(clock_mode):
    radar = MagicMock()
    radar.wait_for_hardware_trigger.return_value = "dump"
    radar.last_hardware_trigger_first_byte_timestamp = 12000.3
    valid_sync = {
        "usable_for_trigger_timestamps": True,
        "best_offset_s": 12000.0,
        "clock_sync_method": "integer_rollover",
        "rollover_uncertainty_ms": 10.0,
        "reads": [{"host_after": time.time(), "radar_clock_s": 0.0}],
    }
    radar.last_clock_sync = None
    radar.read_clock_sync.return_value = {"usable_for_trigger_timestamps": False}
    if clock_mode == "fresh":
        radar.read_clock_sync.return_value = valid_sync
    elif clock_mode in ("previous", "stale"):
        radar.last_clock_sync = valid_sync
        if clock_mode == "stale":
            valid_sync["reads"][0]["host_after"] -= 120.0
    else:
        radar.read_clock_sync.side_effect = OSError("clock unavailable")
    capture = IQCapture(0.0, 0.0256, [2048] * 4096, [2048] * 4096)
    processor = MagicMock()
    processor.parse_capture.return_value = capture
    processor.process_standard.return_value = SpeedTimeline(
        [SpeedReading(100.0, 900.0, 30.0, "outbound")], 937.5
    )

    timestamps_at_rearm = []

    def check_rearm(_rate):
        timestamps_at_rearm.append(capture.trigger_timestamp)
        return True

    radar.rearm_internal_speed_trigger.side_effect = check_rearm

    assert triggers.HardwareTriggeredCapture().wait_for_trigger(radar, processor) is capture
    radar.read_clock_sync.assert_called_once_with(samples=36, store=False)
    names = [call[0] for call in radar.mock_calls]
    assert names.index("read_clock_sync") < names.index("rearm_internal_speed_trigger")
    assert timestamps_at_rearm == [capture.trigger_timestamp]

    if clock_mode in ("fresh", "previous"):
        assert capture.trigger_timestamp == pytest.approx(12000.0256)
        assert capture.trigger_timestamp_source == "ops_clock_sync"
    else:
        assert capture.trigger_timestamp == pytest.approx(12000.3 - (4096 / 30000 - 0.0256))
        assert capture.trigger_timestamp_source == "first_byte"
    radar.rearm_internal_speed_trigger.assert_called_once_with(30)


def test_association_uses_nearest_capture_once_and_keeps_future_capture(tmp_path):
    from openflight.iwr6843.monitor import IWR6843Capture, IWR6843CaptureMonitor

    monitor = IWR6843CaptureMonitor(
        config_path=tmp_path / "unused.cfg",
        output_dir=tmp_path,
        radar=MagicMock(),
        match_tolerance_s=0.75,
    )
    for sequence, timestamp in enumerate([98.0, 99.5, 100.08, 103.1], start=1):
        monitor._captures.append(
            IWR6843Capture(
                sequence=sequence,
                trigger_timestamp=timestamp,
                completed_timestamp=timestamp + 1.0,
                dump_duration_s=1.0,
                raw=b"capture",
                path=None,
            )
        )

    assert monitor.capture_for_shot(100.0, timeout_s=0).sequence == 3
    assert [capture.sequence for capture in monitor._captures] == [2, 4]
    assert monitor.capture_for_shot(102.0, timeout_s=0) is None
    assert monitor.capture_for_shot(103.0, timeout_s=0).sequence == 4
    assert monitor.capture_for_shot(103.0, timeout_s=0) is None
