"""Portable Task Tower entry point after clone."""
import sys

if sys.version_info < (3, 11):
    print("Task Tower requires Python 3.11 or newer. Install it and retry.", file=sys.stderr)
    raise SystemExit(2)

from task_tower.bootstrap import main

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
