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

## Pi checkpoint: IWR firmware flashed (2026-10-09, EDT)

User-provided Pi terminal output confirms:

- Software checked out at `7ed6f5d`; saved Pi Python setting, executable bits
  and bench log restored with `git stash apply` (stash retained).
- Before flashing: IWR 1.0.2, Git `1d23e2fdfab1`, built
  `2026-10-01T19:20:08Z`. Server/kiosk stopped and `/dev/ttyUSB0` unowned.
- ROM bootloader probe passed. Flashed the bundled Cormac image
  `firmware/releases/openflight_iwr6843_v1.0.3.bin`, 518,660 bytes.
- SHA256: `ef03570c4a0d3b94de556935b799ca3cef92e01b9f3b7a8882966d1696baebc1`.
- ROM bootloader verified the completed write. After returning to functional
  mode, the board reported **1.0.3, Git `4e4e9c5d94b7`, hybrid-cadence,
  built `2026-10-09T15:58:05Z`**.
- Camera and display disconnected while replacing the radar front. Next run
  uses the server directly over SSH. OPS firmware has not been changed.
- This verifies firmware installation only. Independent triggering, capture
  association, repeated rearming and TrackMan accuracy are still untested.

Headless startup (keep console evidence alongside session JSONL):

```bash
mkdir -p ~/openflight_sessions
uv run --frozen openflight-server \
  --host 0.0.0.0 --web-port 8080 \
  --port /dev/ttyAMA0 --ops-baud 230400 \
  --trigger hardware --trigger-threshold 25 --trigger-magnitude 25 \
  --pre-trigger-segments 6 \
  --iwr6843 --iwr6843-port /dev/ttyUSB0 --iwr6843-self-trigger \
  --debug --session-location ops221-independent-bench \
  2>&1 | tee -a ~/openflight_sessions/ops221-independent-startup.log
```

## First idle startup: initialization passed, IWR rearm failed

User-provided output from 2026-10-09 22:51 EDT, software `7ed6f5d`:

- Camera/display disconnected; radars loose, supported upright on a coffee
  table and reportedly aimed away from moving objects. This is not an aligned
  golf setup or a controlled RF environment.
- IWR 1.0.3 and OPS 1.3.2 initialized. OPS armed at ST-25 / S#6 / S=30 /
  SM25; server logged independent triggers with no IWR-to-OPS S! forwarding.
- IWR produced three unsolicited captures, each 733,301 bytes in about 7.10 s.
  Each was followed by `l3release` reporting `self-trigger freeze timed out`.
  Two recovery restarts completed in the supplied log; the run was interrupted
  with Ctrl+C during the third recovery.
- OPS reported no dump during its first 30-second wait despite the IWR
  activity. This supports trigger isolation, not OPS capture/rearm acceptance.
- Capture matching and OPS per-shot clock synchronization were not exercised.

Code review lead, not a hardware-confirmed cause: Cormac's `--debug` forces
full IWR `l3dump` readback. That path uses `l3_stopCaptureAtBoundary` and
`l3_trigRearm`, whereas `l3release` uses `l3_awaitFrozenRing`, which explicitly
consumes the freeze completion and clears `gSelfTriggerLatched`. The firmware
and IWR driver/monitor files are unchanged from Cormac `12d6205` in this
experiment. Next comparison: same settings without `--debug`, location
`ops221-independent-idle-no-debug`. No firmware or threshold change yet.

## Idle comparison without debug: IWR release/rearm succeeded

User-provided console log, 2026-10-09 23:01:42 through 23:03:17 EDT,
software `7ed6f5d`, same trigger thresholds, no `--debug`:

- 27 numbered IWR captures, each followed by successful `l3release` rearm.
  Capture bookkeeping took 0.01 s (one took 0.02 s); raw readback was disabled.
  No release timeout or radar recovery restart appears in the supplied output.
- One earlier, unaccepted IWR trigger was released while OPS initialized.
- OPS produced three ordinary 30-second no-dump timeouts and no capture.
  IWR triggers therefore still did not force an OPS capture.
- IWR triggered throughout the run. The user waved an arm near the end,
  reporting an off-axis position about 3-4 ft from OPS; the exact movement
  timestamps were not marked. The denser late trigger cluster cannot be
  attributed conclusively to that motion.
- No onboard metric-result lines appeared. An `onboard result only` capture
  message is not evidence of a valid shot or even a populated result packet.
- Removing debug eliminated the observed rearm failures in this comparison,
  strengthening the full-readback-path hypothesis. It did not eliminate
  unsolicited IWR triggering. OPS capture/rearm, synchronized timestamps,
  sensor matching and shot accuracy remain untested on hardware.

## Hardware and fallback

- Target: Pi 5, OPS243-A firmware 1.3.2 on `/dev/ttyAMA0` at 230400 baud,
  IWR6843LEVM on `/dev/ttyUSB0`.
- Installed Cormac IWR firmware confirmed in the Pi checkpoint above. A Git
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
