# Host sender used for this capture

These are the reviewed host-only scratch sender and its 18 offline tests used for the successful `rx-monitor-02-heltec-off` observation. Their absolute import path records the actual workstation at execution time; they are evidence, not the portable entry point. Use the maintained [`tools/vesc/rx_probe.py`](../../../../../../tools/vesc/rx_probe.py) and project tests for another session.

The first `lisp-contexts-before` inspection used an earlier evidence parser lacking the later ordered-heading/quiet-tail checks; its recorded output nevertheless contains all three headings and no context records. The fixed expressions/framing were unchanged. The complete monitor uses the final reviewed sender archived here. No sender offers arbitrary Lisp evaluation, motor commands, input overrides, firmware writes or resets.
