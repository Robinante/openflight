"""Regression coverage for asynchronous OPS capture/re-arm handling.

The real OPS243-A firmware 1.3.3 bench test on 2026-11-21 established:
reader-first PASS; late reader + input clear FAIL; late reader + preserve PASS.
These focused tests pin the host-side policy. They are not a substitute for
the Pi/UART/IWR hardware validation before merging.
"""

from openflight.rolling_buffer.trigger import SoundTrigger


class IdleRadar:
    """Minimal reader stub; no synthetic radar capture is supplied."""

    def __init__(self, orphaned=False):
        self.last_hardware_trigger_orphaned_dump = orphaned
        self.calls = []

    def wait_for_hardware_trigger(self, **kwargs):
        self.calls.append(("wait", kwargs))
        return ""

    def rearm_rolling_buffer(self, pre_trigger_segments):
        self.calls.append(("rearm", pre_trigger_segments))


def test_iwr_reader_preserves_pending_bytes_and_detects_orphans():
    radar = IdleRadar()
    trigger = SoundTrigger(pre_trigger_segments=24, source="iwr6843")

    assert trigger.wait_for_trigger(radar, processor=None, timeout=0.01) is None
    action, options = radar.calls[0]

    assert action == "wait"
    assert options["discard_pending_input"] is False
    assert options["detect_orphaned_dump"] is True


def test_idle_timeout_does_not_rearm():
    radar = IdleRadar()
    trigger = SoundTrigger(pre_trigger_segments=24, source="iwr6843")

    assert trigger.wait_for_trigger(radar, processor=None, timeout=0.01) is None
    assert [name for name, *_ in radar.calls] == ["wait"]


def test_orphaned_dump_rearms_and_records_diagnostic():
    radar = IdleRadar(orphaned=True)
    trigger = SoundTrigger(pre_trigger_segments=24, source="iwr6843")

    assert trigger.wait_for_trigger(radar, processor=None, timeout=0.01) is None
    assert radar.calls[-1] == ("rearm", 24)
    diagnostics = trigger.drain_diagnostics()
    assert any(
        item.get("reason") == "orphaned_dump" and not item.get("accepted")
        for item in diagnostics
    )


def test_sound_gate_reader_also_preserves_queued_bytes():
    radar = IdleRadar()
    trigger = SoundTrigger(pre_trigger_segments=12, source="sound")

    trigger.wait_for_trigger(radar, processor=None, timeout=0.01)
    options = radar.calls[0][1]
    assert options["discard_pending_input"] is False
    assert options["detect_orphaned_dump"] is True
