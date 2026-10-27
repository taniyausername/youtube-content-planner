#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
if command -v python3.12 >/dev/null 2>&1; then
    python3.12 start.py
else
    python3 start.py
fi
result=$?
if [ "$result" -ne 0 ]; then
    read -r -p 'Press Return to close this window.'
fi
exit "$result"
