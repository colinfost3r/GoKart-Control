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
