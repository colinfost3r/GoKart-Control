# GoKart Control project conventions

- Canonical project: ~/Projects/50 Day/GoKart Control/ (Eamon's clone: ~/GoKart-Control).
  Reuse this repository.
- Read README.md and HANDOFF.md before implementation; inspect local git status.
- The connected kart's measured baseline takes precedence over the old M5Stack
  repository for existing hardware/settings. User requirements govern desired behavior.
- Preserve evidence in hardware/vesc/. Never mutate an existing baseline capture.
- Read-only controller inspection is authorized; do not silently include motor
  commands, configuration writes, firmware updates, resets or motor detection.
- Maintain separate verified/reported/proposed status. Runtime reads are not
  automatically saved-flash backups. Motor-temperature sensors are not wired.
- The Heltec owns the VESC connection, GPS, LoRa and supervisory profile logic.
  The kart Pi is display/interface only. BLE remains the preferred VESC transport.
  Driver inputs and motor control remain with the ESC. Installed read-only milestones keep
  writes disabled until the requested control build is commissioned.
- Reliability first: no driving-state changes on display/Heltec/link loss or
  reconnect. Keep current active VESC settings; no saved-profile restore,
  heartbeat-dependent driving lease, stop/reset or cached-command replay.
  Reconnect read-only and reconcile actual state. Existing ESC protections remain
  intact. This supersedes the earlier saved-configuration fallback requirement.
- Owner decision 2026-11-10: enable M5 mode selection AND full existing Eamon base-station
  controls (mode, STOP/START, SLOW/BOOST/RACE and game commands). Keep temporary writes store=0,
  fresh identity/config checks and no reconnect replay. Do not treat telemetry tests as motor tests.
- Owner also requests checking all motor/app settings and aligning kart 3's tune with the kart 2
  baseline; owner confirms same motor, battery/BMS, gearing and wheels. Capture all settings first,
  preserve controller/motor/pedal calibration and identities, and document the actual named-field
  changes. A runtime export is not proof of saved flash. No blind whole-config import.
- Explicit maintenance exception recorded 2026-11-10: owner requested a Desktop backup and a
  calibration-preserving tune trial. Twelve named motor fields were applied once with persistent
  SET_MCCONF and exact 376-field readback; all app/calibration bytes preserved. Do not rerun the
  old trial or infer permission for arbitrary future tuning. Supervisory writes remain temporary.
- Explicit maintenance exception 2026-11-11: owner requested persistent motor `l_current_min`
  0 to -5 A after a successful supervised RAM trial; only this field changed and all other
  375 fields were preserved. Consult HANDOFF for cold-boot/Heltec acceptance. Karts 4/5 are
  the next copies of kart 3; karts 1/2 remain Eamon's test units. Preserve each target
  calibration/identity; fleet preparation is offline and does not authorize blind imports.
- Explicit maintenance exception 2026-11-13 (kart 4 only): after reviewing kart 4's read-only
  capture the owner approved one persistent SET_MCCONF carrying the twelve reviewed tune fields
  plus five protection limits set to kart 3's values (`l_in_current_min`, `l_abs_current_max`,
  `l_min_vin`, `l_max_vin`, `m_fault_stop_time_ms`). Applied once with
  `tools/vesc/apply_fleet_tune.py`, exact 376-field readback, cold-boot check; see
  hardware/vesc/kart4/2026-11-13/. Kart 5 needs its own capture, review and approval. Do not
  infer permission for other fields, controllers or a repeat of this write.
- Explicit maintenance exception 2026-11-13 (kart 4 only): the owner decided to install the
  reverse-input filter on kart 4 and approved the write after its switch was observed in both
  positions. Stored once with `tools/vesc/fleet_rx_filter.py` (kart 3's tested core, kart 4's
  UUID in the startup guard), read back exactly, and verified armed after a power cycle; see
  hardware/vesc/kart4/2026-11-13/filter/. There is no tested removal tool.
- Explicit maintenance exception 2026-11-13 (kart 5 only): after reviewing kart 5's own capture
  the owner approved one persistent SET_MCCONF (the twelve reviewed tune fields plus the
  protection limits; on kart 5 only `l_abs_current_max` of those differed) and then the
  reverse-input filter install, each with its own go-ahead. The tune write's exact read-back
  failed on one controller-measured voltage offset and was not retried; independent captures
  and a cold boot confirmed the intended values. See hardware/vesc/kart5/2026-11-13/. Do not
  repeat either write or extend this to other fields or controllers.
- Observed 2026-11-13, unresolved: kart 5's bus read 86.4 V for two samples at the end of an
  uncapped wheels-up run near 34700 ERPM with the pack at 83 V. No fault (`l_max_vin` is 90 V on
  karts 3-5). The tune is common to karts 3-5; treat uncapped full-pedal running on a near-full
  pack as an open tune question for the owner and Eamon, and do not change limits to chase it
  without their decision.
- Owner decision 2026-11-12 (native game rules): the host ("game maker") chooses the speed its
  course is played at, ECO or NORMAL. Joining writes that mode and locks the joined kart's mode
  buttons to it; pit commands still win. A boost is a step up from the mode in force (BOOST one
  mode up; ROCKET and STAR the top mode), never an absolute scale. See docs/m5-player-mode.md.
- Explicit owner exception 2026-11-12 to "reconnect read-only": a timed boost whose END could not
  be written or confirmed is finished once per VESC link session after the controller is freshly
  verified, and after a Heltec restart that left its own boost on the controller. Lower-only (it
  may never raise the current scale or the speed cap), never under STOP/GRID, no command replay.
  This covers boost ends only. Do not extend it to SLOW endings, modes or any other write.
- Driver messages and future safety geofence enforcement remain deferred. M5 game-zone UI parity
  is separate from enabling the existing Heltec/base command implementation.
- The owner now explicitly authorizes ongoing commits/pushes at coherent, checked
  milestones so Colin and Eamon share current work. This supersedes the earlier
  per-commit request rule for this project. Fetch before work and again before push;
  inspect and integrate remote changes without overwriting others or force-pushing.
  Use focused branches/worktrees and PRs for parallel implementation; see CONTRIBUTING.md.
- Keep requirements, architecture, config and handoff consistent. Preserve evidence;
  distinguish owner decisions from proposed details and verified implementation.
- No sub-agent delegation is required by this file.
- Run offline checks described in CONTRIBUTING.md for inspection-tool changes, and
  tools/run_tests.sh (all suites) before every push.
