#!/bin/bash
source "$(dirname "$0")/venv/bin/activate"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
