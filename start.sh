#!/bin/sh
set -eu
if ! command -v python3 >/dev/null 2>&1; then
    echo 'Task Tower requires Python 3.11+. Install it and retry.' >&2
    exit 2
fi
exec python3 "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/bootstrap.py" "$@"
