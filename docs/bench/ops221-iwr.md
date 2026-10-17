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

## Direct OPS captures and early-dump preservation (October 9-10)

Human bench tests on software `7ed6f5d`, OPS 1.3.2, UART 230400 baud:

- After a reboot, the desktop TrackMan kiosk restarted and owned the OPS UART.
  Concurrent diagnostic access produced garbled replies and read errors. The
  user stopped the kiosk and verified both radar ports were free before the
  direct captures below. Earlier post-reboot readbacks are inconclusive.
- Direct scripts configured a temporary 200 mph guard, set the final minimum
  speed filter, cleared input before arming, then wrote the final ST threshold
  and read continuously for 30 seconds. No S!, additional PA, IWR trigger, or
  persistent-settings write was used. The scripts requested PI on exit.
- The immediate "Receiving" message could be the ST acknowledgement, not the
  capture. Host arrival timing was not recorded. These are one-shot tests,
  not repeated-rearm validation or golf-shot acceptance.

| Settings (mph / SM / S#) | Observation | File in `~/openflight_sessions` |
| --- | --- | --- |
| 5 / 25 / 6 | Stationary: complete I/Q dump | `ops-direct-trigger_20261009_233447.txt` |
| 5 / 25 / 6 | Arm-wave attempt: complete dump; motion timing uncertain | `ops-direct-trigger_20261009_233607.txt` |
| 25 / 25 / 6 | Only ST acknowledgement in 30 seconds | `ops-direct-trigger-25mph_20261009_234537.txt` |
| 20 / 20 / 4 | Stationary: complete I/Q dump | `ops-vendor-baseline_20261009_235202.txt` |
| 20 / 25 / 4 | Stationary: complete dump reported by user | `ops-20mph-sm25-s4_20261010_000411.txt` |

The first three uploaded dumps (both 5 mph runs and the SM20 run) contain valid
JSON and 4096 samples per channel, without ADC clipping. Offline mean-removed,
Hann-windowed complex FFT analysis at 30 ksps shows recurring low-frequency
structure near 2.34 mph equivalent. The SM20 run's I standard deviation was
94.0 ADC counts versus 33.7 in the first stationary run; Q was 44.3 versus
41.4. The signal changed as well as the settings; no physical noise source or
firmware fault has been established. Both 20 mph configurations triggered
without deliberate movement. One quiet 25 mph interval is not a false-trigger
rate measurement.

OPS AN-027-C specifies 30 ksps for golf and a default SM20. OPS golf-test notes
quoted in PR221 use a 20 mph example and suggest S#4 after observing excess
prehistory with S#8. Combining these is a guidance-based baseline, not a fully
documented vendor test preset. PR221 separately reports testing 25 mph, SM25,
and S#6; experimental defaults remain unchanged.

Code regression: input resets after initial ST arming, after rearming, and at
entry to the wait loop could delete an already-arriving capture. Simulated
immediate dumps were discarded at both arming points before the fix. The
internal-trigger path now preserves pending bytes and lets the existing
capture-boundary detector discard command replies. Sound-trigger waits retain
their previous input-clearing behavior. History-fill waits now run under the
temporary guard, before the final ST command, avoiding deliberate post-arm
delays while UART data can accumulate. This fixes a demonstrated software
data-loss path, not the unexplained physical idle triggers.

Validation: 578 targeted tests passed, one skipped (missing fixture), covering
OPS, rolling-buffer strategies, independent triggers, and server integration.
The user then validated `a81bff5` on the Pi at 00:13 on October 10, with
20 mph / SM25 / S#4 and IWR disabled. OpenFlight received 41,035 bytes,
reported GC rearming, and rejected the capture because it contained no
outbound speed >=35 mph. Three subsequent 30-second waits were quiet.
This confirms one integrated receive/reject/rearm cycle; a second capture
after rearming and golf-shot accuracy remain untested. Evidence:
`ops221-preserve-20mph.log`, `session_20261010_001333_ops221-preserve-20mph.jsonl`,
and `radar_raw_20261010_001333.log` in `~/openflight_sessions`.

## IWR overnight investigation (October 10)

At the overnight checkpoint, repeated unsolicited triggers remained unresolved
and no physical IWR capture from this bench run was available locally for replay. The previously recorded
no-debug run eliminated the full-dump release errors, but still generated
unwanted triggers. Neither this experiment nor its tests establish hardware
readiness for TrackMan.

One separate host race was reproduced and fixed: the firmware emits
`Triggered` before collecting the post-impact tail and setting result
`ready=1`. The host previously queried the result once, then read/released
the ring even when the reply was `ready=0`. That loses the eventual onboard
result and can explain missing metrics, but is not established as the cause
of the firmware's unwanted trigger decisions. The host now retries not-ready
results at 20 ms intervals within a 250 ms budget. Existing per-command serial
timeouts still apply; a stalled command can exceed that polling budget.
Unreadable or persistently absent results still allow capture/rearm and log
a warning. No firmware binary, trigger sensitivity, calibration, or shot
acceptance threshold was changed. No reflash is needed for this host fix.

Validation:

- Both new regressions failed before the fix: delayed results were lost,
  and not-ready replies were never retried. All 110 monitor tests now pass.
- Driver, independent-trigger, and compiled firmware replay suites: 200 passed,
  four failed. The same four recording-expectation failures reproduce on an
  isolated checkout of `a81bff5`: one minimum club-point expectation, two
  post-impact club-track cases, and one late-trigger expectation. They are
  not fixed or weakened in this change.
- Ruff lint and formatting checks pass for the changed Python files.
  Monitor pylint scores 9.97/10 (existing module size/argument warnings).
- A bounded synthetic-noise experiment exercised the compiled C replay path:
  seeds 0-3, 800 frames each, 2 ms period, 36 chirps, four RX, 53 bins starting
  at bin 20, independent Gaussian I/Q sigma 30; tee bin 36, band six bins,
  SNR 1 and 4. None of the eight runs fired. This short, idealized noise model
  does not cover the board's interference, structured clutter, or scheduling;
  it does not justify changing sensitivity.

Source inspection also found that full `l3dump` uses a different freeze/rearm
path from `l3release`: its chained-ring restart does not clear the self-trigger
latch. That is consistent with the debug-only release timeout, but has not
been confirmed with a firmware patch on hardware. Continue bench validation
without `--debug`; the constant-trigger problem still needs actual evidence.

The next evidence requested was the existing `.l3dump` files from the 22:51 debug
run in `~/openflight_sessions/iwr6843`, together with its startup log. These
may expose the physical signal behind the triggers without another firmware
flash. A patched no-debug run should show either `Onboard result: ...` or
the explicit not-ready warning before rearming. A quiet idle interval and
several successive real shots are still required before calling this fixed.

## Morning bench results and TrackMan preparation (October 10)

Times below are the Pi's local time (America/New_York). Tested software:
`a6eb5ac7` on `bench/ops221-iwr-2026-10-09`. OPS firmware is 1.3.2;
IWR firmware is 1.0.3, git `4e4e9c5d94b7`, built October 9 at 15:58:05Z.

### Replay of the actual bench captures

The user supplied `iwr-trigger-evidence.tar.gz`, containing the startup log
and three 733,301-byte IWR dumps from October 9 at 22:51:19, 22:51:29 and
22:51:38. All decode as 24 frames, 36 chirps, four RX, 53 range bins and a
2 ms frame period. These raw files have not been added to the repository.

Replay used the compiled C detection code, tee bin 36, a six-bin tee band
and the logged SNR setting. Applying the repository reference calibration
also preserved the trigger outcomes below. Replay starts from the retained
capture, not the board's complete preceding detector history.

| Trigger SNR (linear multiplier) | Bench captures firing in replay | 20-swing comparison |
| --- | --- | --- |
| 1.0 | 2 of 3 | 20 triggered |
| 1.25 | 0 of 3 | 20 triggered, same frames as 1.0 |
| 1.5 | 0 of 3 | 20 triggered, same frames as 1.0 |

The two reproduced events fired the club range-crossing rule on frame 6.
Their fitted range speeds were approximately 50 and 55 m/s, formed from
weak tracked returns; neither replay produced a ball track. These are
detector interpretations, not measured golf swings or an identified physical
interference source. The first capture's original trigger did not reproduce.
The positive comparison used the existing August 24 corpus of twenty
24-frame captures with tee bin 38, six-bin band, stop-at-fire and
post-impact processing disabled. Detection parity is not accuracy validation.

### Pi tests with independent triggers

- The desktop boot launcher still used `--trigger sound --debug`. It was
  stopped, and both serial ports were verified free before testing.
- At 09:25, startup failed on IWR `sensorStop` with a self-trigger freeze
  timeout, before the new SNR was applied. A physical IWR RESET cleared the
  condition; no firmware was reflashed.
- SNR 1.25: six IWR captures appeared in the first approximately 90 seconds.
  All returned onboard results and successfully rearmed through `l3release`.
  This did not establish a quiet idle baseline; motion was not precisely
  annotated for that run. OPS reported no dumps.
- SNR 1.5: the user explicitly marked a still interval from 09:32:31 to
  09:33:31 with zero IWR captures. During waving from approximately 09:33:31
  to 09:34:07, three captures appeared at 09:34:03.888, 09:34:06.489 and
  09:34:07.275. Results were invalid, invalid and partial; each completed in
  0.04-0.05 seconds and rearmed successfully. The following still interval
  through 09:35:01 was quiet. OPS remained quiet throughout.

This supports using SNR 1.5 for the next field experiment. It does not prove
false triggers eliminated or golf-shot sensitivity. The approximately
33-second wait during waving is not a measured processing latency. OPS
30-second timeout messages mean no capture, not an OPS trigger event.

Evidence under `~/openflight_sessions`:
`ops-iwr-snr125.log`, `session_20261010_092638_ops-iwr-snr125.jsonl`,
`ops-iwr-snr150.log`, `session_20261010_092931_ops-iwr-snr150.jsonl`,
and their `radar_raw_20261010_092638.log` / `radar_raw_20261010_092931.log` logs.

### Prepared boot configuration

At 09:40 the user updated the Pi-local `~/.config/labwc/autostart` after
backing it up as `autostart.bak-20261010-094036`. Its launcher now uses:

```bash
exec env OPENFLIGHT_UV_RUN_ARGS=--no-sync bash ./scripts/start-kiosk.sh \
  --radar-port /dev/ttyAMA0 --ops-baud 230400 \
  --trigger hardware --trigger-threshold 20 --trigger-magnitude 25 \
  --pre-trigger-segments 4 \
  --iwr6843 --iwr6843-port /dev/ttyUSB0 \
  --iwr6843-self-trigger --iwr6843-self-trigger-snr 1.5 \
  --camera-capture --ble --session-location trackman
```

Mock mode and `--debug` are absent. The kiosk syncs the camera and BLE extras;
`--no-sync` on its subsequent `uv run` preserves that prepared environment.
The user successfully ran `uv sync --frozen --extra camera --extra ble` and
imported `picamera2`, `cv2` and `bless`. That verifies dependency availability,
not camera operation or BLE advertising. Camera and display were still to be
reconnected, with power removed, during enclosure reassembly.

Camera capture follows IWR trigger notifications in this configuration.
BLE supports shot delivery, club/profile selection and power status in this
branch; its command dispatcher does not expose IWR calibration. Use the kiosk
for setup/calibration. Camera defaults request 640x400 at 300 fps; achieved
capture rate and saved clips must be checked after reconnecting the hardware.

Remaining gates: verify the new boot command after reassembly, repeat the
stationary check, confirm actual camera captures and phone BLE connection,
then check several separated real shots against TrackMan for detection,
sensor association and measurements. No TrackMan acceptance is claimed.

## October 17: upstream PA re-arm backport

Backported the trigger fix from upstream PR #221, commit
`c4715a469504f6fe19f5f5b1a5e000b907870ca7`. Completed OPS dumps now
re-arm with `PA`, keeping firmware 1.3.2 detector settings intact. Orphaned
dump tails are detected and re-armed instead of leaving the board idle.
The bench branch retains its immediate UART reads, pending-input option,
independent OPS/IWR triggers and clock queries before re-arm. No firmware,
calibration, sensitivity or launcher settings changed.

Windows development validation:

- Driver, rolling-buffer and independent-trigger suites: 242 passed.
  Eight focused assertions failed before the port and pass afterward.
- Related UART, re-arm, mode-command, serial-deadlock, server, IWR monitor
  and kiosk suites: 504 passed, 46 skipped, one failed. The calibration-path
  assertion compares Windows backslashes with forward slashes; it also
  fails on a clean archive of unchanged `db22835`. Linux kiosk tests skip
  on Windows; no Pi acceptance is claimed.
- Changed-file Ruff lint passed; Pylint for both implementation files:
  9.84/10. Ruff formatting differences in `ops243.py` and `test_ops243.py`
  also exist on unchanged `db22835`; the other changed Python files pass.

Cormac's current `feat/iwr-calcs`, `109c259`, adds the swing zone to
replay and the dump viewer. Its commit and azimuth-check guide explicitly
state that the board trigger does not call it yet and the starting zone
limits require bench calibration. That tooling was not pulled into this
range update; it would not change live triggering.

Pull this branch with `git pull --ff-only origin bench/ops221-iwr-2026-10-09`
from the existing Pi checkout, then restart the existing kiosk launcher.
Keep the prepared October 10 flags, including the no-debug setting.
No reflash is needed. Before shots, repeat rapid-motion OPS re-arming and
the quiet-idle check; look for `Internal speed trigger re-armed (PA)`.
Codex adapted the upstream port and ran the checks above. Hardware retesting
of this backport remains pending.

## October 17: full-dump recording compatibility

The installed 1.0.3 firmware's full `l3dump` restarts sampling without clearing
`gSelfTriggerLatched`. Its next `l3release` waits for a freeze that is no longer
pending and reports `self-trigger freeze timed out`. That exact firmware error
clears the latch before returning. For a full self-trigger readback, the host
now retries `l3release` once: the second command can freeze the running ring
normally and re-arm it. Any further error retains the existing restart fallback.
No firmware image was changed. This is a host compatibility workaround;
hardware confirmation on the installed board is still required.

OPS hardware-dump responses are now written to the existing `radar_raw_*.log`
before shot acceptance, retaining I/Q arrays even when a capture is rejected.
Accepted shots continue to include structured arrays in the session JSONL.

Validation: the simulated IWR timeout/recovery and missing OPS raw-log
regressions failed before these changes. Related driver, monitor, trigger
and session suites: 431 passed. Camera/capture/replay suites: 73 passed.
Changed-file Ruff lint passed; monitor and its tests pass formatting.
Pylint for the two changed implementation modules: 9.93/10. No physical
radar or camera validation was performed for this recording workaround.

For recording, add `--debug` to the prepared launcher, alongside the existing
`--camera-capture`. Keep `--iwr6843-veto-no-ball` absent so a rejected onboard
result does not skip the raw IWR dump. This supersedes the no-debug advice
for the earlier host version above, subject to a Pi recording check.
OPS raw logs and session JSONL go to `~/openflight_sessions`; IWR dumps go
to its `iwr6843` folder, and camera frame archives to `trackman/camera`
when the existing `--session-location trackman` is used. Recording is triggered,
not continuous: full IWR readback previously took approximately seven seconds,
during which another IWR capture cannot be recorded. No promise of capturing
every swing or eliminating sensor false triggers is made.

When renaming `openflight-cormac` to `openflight-bench`, recreate its virtual
environment with `/usr/bin/python3` and system site packages enabled so the
Pi-provided Picamera2 remains accessible. Preserve the old environment until
the rebuilt one imports `picamera2`, `cv2` and `bless` successfully. Update
the desktop autostart's checkout path before rebooting. Renaming the separate
workbench checkout to `radar-workbench` also requires checking its launchers.

Codex implemented and verified the compatibility workaround and raw logging.

## October 17: reversed LIS3DH mounting

The user read WHO_AM_I `0x33` at I2C bus 1, address `0x18`. A marked
front-edge-up tilt moved Y from approximately zero to -0.28 g, producing
about -16 degrees; returning level restored approximately zero pitch.
This confirms a working sensor with a reversed mounting direction.

Use `--inclinometer --inclinometer-pitch-sign -1` for this enclosure. The
default sign remains +1 for other mountings. The service retains raw pitch
and applies `sign * raw_pitch + zero_offset` to the calibrated pitch;
the sign is included in session configuration and per-shot provenance.
No new zero offset or physical sensor change was made. The old boot launcher
did not enable the inclinometer at all.

Four new sign/validation tests failed before implementation. Inclinometer,
server and readiness suites after the change: 373 passed, one fixture skip,
one previously confirmed Windows path assertion deselected. The sensor
readout above is real Pi evidence; running the new sign option on the Pi
and verifying the resulting correction remain pending.

## October 17: capture readiness in the kiosk

Live now shows a persistent READY / WAIT / DISCONNECTED strip, with OPS,
IWR and camera states and an explicit Raw IWR on label. Host capture,
processing, serial work, re-arming, worker errors and stopped workers
prevent green readiness. Polling uses an HTTP snapshot every 500 ms,
does not issue radar commands and clears the display to CHECKING RADARS
if updates fail. This reports host readiness, not a separate RF health test.
The IWR capture remains busy through its final re-arm check. OPS hardware
waits now report their first byte and accept shutdown cancellation, as the
sound path already did; a failed OPS re-arm stays marked recovering.

Backend radar/server/readiness/camera checks: 672 passed, one missing-fixture
skip and the previously confirmed Windows path assertion deselected.
Later inclinometer/server checks: 373 passed with the same skip/exclusion.
UI: 263 unit tests, type-check, production build and changed-file lint passed.
Browser tests passed at 800x400, 800x480 and 1024x600, covering busy, recovery,
restored readiness, failed polling and visible metrics; the smallest screenshot
was visually inspected. These browser checks used a simulated backend.
Pylint for all changed implementation modules: 9.80/10. Physical capture and
recovery indications still require confirmation after updating the Pi.

The kiosk Record/Stop recording button changes debug logging, not the IWR
monitor's startup readback setting. Start with `--debug` and leave it enabled
for this raw-recording session. Runtime switching of IWR readback was not added.

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
clock synchronization, implemented the IWR result wait, analyzed the supplied
captures, and ran the automated checks above. The user performed the reported
Pi bench tests and launcher update. Human code review, post-reassembly checks
and real-shot TrackMan validation remain pending; these results are not full
hardware acceptance.
