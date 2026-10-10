# OPS self-trigger / IWR integration experiment

Personal experiment on `Robinante/openflight`, branch
`bench/ops221-iwr-2026-10-09`. No upstream submission or hardware acceptance yet.

## Checkpoint 1: merge OPS trigger support

- Base: Cormac `feat/iwr-calcs` at `12d6205aa72eb63ea7f5a46a2a8a0ac8b215edbd`.
- Merged: OpenFlight PR #221 at `73eacc7de9d96e607b239f4ac58be49f6c97ea1e`.
- Resolved six conflicting files, retaining tests from both branches.
- Combined trigger option routing: sound/IWR captures retain Cormac's source
  labels and buffer split; OPS hardware captures receive their own threshold,
  magnitude and split; host speed mode receives only its own settings.
- PR #221 already requires OPS firmware 1.3.2 or a later 1.3.x patch release.
  Its PR description still refers to the original 1.3.1 requirement.
- Added coverage for default, zero and explicit hardware thresholds with a
  conflicting sound buffer setting. Existing CLI tests exposed incorrect
  routing before the fix (three failures).

### Validation (development container, not the Pi)

- `uv run pytest tests/test_ops243.py tests/test_rolling_buffer.py tests/test_server.py tests/test_start_kiosk.py -q --tb=short`:
  603 passed, one skipped, one failed. The skipped test needs a session fixture
  absent from this checkout. The failing kiosk process-tree shutdown test timed
  out after 30 seconds; it also fails in isolation on unmodified Cormac
  `12d6205` in this container. No assertion was disabled or weakened.
- After adding three threshold cases,
  `uv run pytest tests/test_server.py::TestHardwareTriggerPlumbing tests/test_server.py::TestSelfTriggerCli -q --tb=short`:
  45 passed.
- Ruff lint passed for `ops243.py`, `rolling_buffer/`, and `server.py`.
- `uv run pylint src/openflight/ --fail-under=9`: 9.76/10.
- Ruff format check reported one inherited multiline log-string formatting
  difference in PR #221's `ops243.py`; left unchanged.
- No radar, camera, Pi kiosk, power or TrackMan testing performed for this checkpoint.

## Next checkpoint

`--trigger hardware` adds OPS self-trigger support, but combining it with
`--iwr6843-self-trigger` is still rejected by the existing CLI guard. Do not
remove that guard alone: the IWR observer currently sends `S!` to the OPS.

Next work: separate that observer from independent IWR detection, verify
timestamp handling and capture association, then test on the Pi. Camera
self-trigger is not implemented by this merge.

## Hardware and fallback

- Target: Pi 5, OPS243-A firmware 1.3.2 on `/dev/ttyAMA0` at 230400 baud,
  IWR6843LEVM on `/dev/ttyUSB0`.
- Installed IWR firmware must be confirmed before hardware testing. A Git
  checkout does not flash either sensor.
- Jamorro fallback: software at `2a895d65decb7e659ccb2520f847ef2d7289a180`
  with its own matching IWR binary. Cormac and Jamorro both label different
  binaries 1.0.3; retain the originating commit when recording firmware.
- Preserve the October 4 Pi branch and the stash named
  `Pi bench setup before OPS221 integration 2026-10-09`.

## Assistance

Codex resolved the merge, adapted trigger option routing, and ran the automated
checks above. Human code review and real hardware/TrackMan validation remain
pending; these results are not hardware acceptance.
