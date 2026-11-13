# Exact session tools and source

These are the source files used during this trial, archived after the captures.
The RAM loader and lifecycle helper were run from scratch locations; their portable
maintained versions now live in `tools/vesc/`. Path resolution changed, control logic
and deployed expressions did not. Use the maintained tools for future work.
`rx_failure_trace.py` imported the maintained project `rx_probe.py` using PYTHONPATH.
The source and dependencies are retained with hashes in inventory.json. Raw attempted
frames in each capture remain the authority for what was actually sent.

No STREAM139, flash/configuration write, reset, throttle override or host motor
command was sent. The one explicit start changed the reverse-button path in RAM.
Initial live-PID verification failed inconclusively; no start was repeated. Later
at-rest direction transitions and positive PID listings resolved that uncertainty.
