"""Test report helper: runs pytest and prints a requirement-coverage summary."""
from __future__ import annotations

import argparse
import subprocess
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--perf", action="store_true")
    parser.add_argument("--container", action="store_true")
    args = parser.parse_args(argv)
    cmd = [sys.executable, "-m", "pytest", "-q", "--cov", "--cov-report=term-missing"]
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        return proc.returncode
    if args.perf:
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-m", "perf"],
                              check=False)
        if proc.returncode != 0:
            return proc.returncode
    if args.container:
        print("container tests: run `make container-test` with docker compose up")
    print("report OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
