#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if pgrep -af 'python3 app/main.py' >/dev/null 2>&1; then
    echo 'El bot ya está ejecutándose.'
    exit 0
fi

python3 -m pip install --disable-pip-version-check -q -r requirements.txt >/dev/null 2>&1
python3 app/main.py
