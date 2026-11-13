"""Run reverse-input cases using an already built, pinned LispBM host runner.

No serial ports, devices, or network access. This does not validate MCU timing.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path, help="New directory for cases and logs")
    args = parser.parse_args()
    runner = args.runner.resolve(strict=True)
    output = args.out.resolve()
    subprocess.run([sys.executable, "-B", str(Path(__file__).with_name("generate_cases.py")),
                    "--out", str(output)], check=True)
    results = []
    for case in sorted(output.glob("test-*.lisp")):
        command = [str(runner), "-h", "2464", str(case)]
        try:
            run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, timeout=45)
            log = run.stdout
            # The pinned upstream harness deliberately returns 1 for success.
            passed = run.returncode == 1 and "Test: OK!" in log and "Result: t" in log
            code = run.returncode
        except subprocess.TimeoutExpired as error:
            log = error.stdout or ""
            if isinstance(log, bytes):
                log = log.decode("utf-8", errors="replace")
            log += "\nHOST TEST TIMEOUT\n"
            passed, code = False, None
        case.with_suffix(".log").write_text(log)
        results.append({"case": case.name, "passed": passed, "returncode": code,
                        "sha256": sha256(case)})
        print(f"{'PASS' if passed else 'FAIL'} {case.name}")
    source = Path(__file__).resolve().parents[1]
    source_hashes = {name: sha256(source / name) for name in (
        "rx-monitor-compact.repl", "rx-monitor-30s.lisp", "rx-filter-candidate.lisp")}
    manifest = {"recorded_at": datetime.now(timezone.utc).isoformat(),
                "firmware_source_commit": "f7c2b34e1cff2234cae98be3abf0cd50e249558f",
                "host_runner_sha256": sha256(runner), "heap_cons_cells": 2464,
                "limitation": "Host interpreter with mocked hardware; other memory pools and timing differ from MCU.",
                "sources": source_hashes, "results": results}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    passed = sum(result["passed"] for result in results)
    print(f"{passed}/{len(results)} passed; logs: {output}")
    return 0 if results and passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
