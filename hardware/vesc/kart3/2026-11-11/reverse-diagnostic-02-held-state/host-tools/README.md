# Session helper inventory

These are the scratch files available when the session was archived. The scratch
snapshot helper produced the first two direct snapshots. The trace helper observed
only fixed identity/GET_VALUES/input-monitor responses and sent no motor commands.
Its console formatting was shortened between the reverse and forward captures;
the earlier exact file was not preserved. No source hashes were embedded at run
time. Do not claim these are byte-for-byte proven sources for every capture.

The archived snapshot helper hardcodes the original worktree path and predates the
maintained typed float parser. It is historical evidence, not a portable entry point.
Use tools/vesc/rx_probe.py for maintained fixed input observations. The trace source
and its 11 mocked transport tests remain archived for review, not automatic motor
acceptance. Operator readiness was checked in the chat; the helper has no throttle
output or host-driven motor test. Raw transmitted frames and immutable manifests
are the record of the actions actually sent. The one-off fixed terminal reader
was not preserved as a standalone script; its exact command frames are retained
in terminal-before-trace/manifest.json.
