#!/usr/bin/env bash
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
(sleep 2; (xdg-open http://127.0.0.1:5000 || open http://127.0.0.1:5000) >/dev/null 2>&1) &
.venv/bin/python app.py
