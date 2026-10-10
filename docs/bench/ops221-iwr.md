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

## Checkpoint 2: independent OPS and IWR triggers

- Allows `--trigger hardware --iwr6843 --iwr6843-self-trigger`.
  IWR captures and rearms its own ring without sending `S!` to OPS.
  The existing `--trigger sound` + IWR software-trigger behavior is retained.
- Shares Cormac's clock-sync selection with OPS internal-trigger captures:
  fresh qualified sync, then a qualified saved sync no older than 60 seconds,
  then first-byte timing. Clock queries finish before OPS rearm; rejected
  captures skip synchronization. Startup information is read before arming,
  and startup clock queries are deferred until a completed dump leaves OPS idle.
- Keeps the existing nearest-capture matcher (within +/-0.75 seconds, consumed
  once). Tests cover stale captures, nearest selection and future captures.
  This is time-based association, not proof that two detections are one swing:
  false triggers inside the window and missing captures need TrackMan validation.
  IWR timestamps remain host receipt times for firmware notices; only OPS has
  this clock mapping. The shot's `impact_timestamp` remains its OPS trigger
  anchor; the separate FFT impact estimate is not substituted in this experiment.
- Debug logs label the independent timing offset separately from `S!` latency.
  Existing JSONL captures retain OPS timing source/offset and IWR notice times.
- Camera autonomous triggering is not implemented. No firmware was flashed.

### Validation (development container only)

- Ten new tests cover CLI acceptance, trigger isolation, sound-mode preservation,
  startup query ordering, clock fallback/rearm ordering and capture association.
  The initial checks reproduced seven failures; a later startup-query regression
  also failed before its fix. Existing rejection tests now assert no clock query.
- `uv run pytest tests/test_independent_triggers.py tests/test_ops243.py tests/test_rolling_buffer.py tests/test_server.py tests/test_iwr6843_monitor.py -q --tb=short`:
  680 passed, one missing-session-fixture skip.
- `uv run pytest tests/test_start_kiosk.py tests/test_iwr6843_runtime_club.py -q --tb=short -k 'not test_stop_kiosk_browser_kills_the_launched_tree_and_spares_other_instances'`:
  66 passed; the one deselected kiosk test has the baseline timeout documented above.
- Four hardware-trigger tests rerun after adding rejection assertions.
- Ruff lint and format checks passed for the changed implementation and new tests.
- `uv run pylint src/openflight/ --fail-under=9`: 9.76/10.
- No Pi, radar, camera or TrackMan validation yet.

### Planned bench command (after firmware verification)

```bash
bash ./scripts/start-kiosk.sh \
  --radar-port /dev/ttyAMA0 --ops-baud 230400 \
  --trigger hardware --trigger-threshold 25 --trigger-magnitude 25 \
  --pre-trigger-segments 6 \
  --iwr6843 --iwr6843-port /dev/ttyUSB0 --iwr6843-self-trigger \
  --debug --session-location ops221-independent-bench
```

This uses real sensors, no mock/BLE/camera flags. The OPS path from PR #221 sets
P0 (full transmit power), 30 ksps, S#6 (~25.6 ms before the trigger), and accepts
outbound captures at least 35 mph. These are initial bench settings, not tuned
TrackMan results. Retain the session JSONL and console debug output; inspect
unmatched captures, timing source/offset, false triggers and repeated rearming.
Verify the installed IWR firmware against this Cormac checkout before running.

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

Codex resolved the merge, implemented independent trigger routing and shared
clock synchronization, and ran the automated checks above. Human code review
and real hardware/TrackMan validation remain pending; these results are not
hardware acceptance.
