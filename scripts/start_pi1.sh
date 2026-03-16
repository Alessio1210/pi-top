#!/bin/bash
cd "$(dirname "$0")/.."
source venv/bin/activate
python3 backend/main.py &
cd frontend && npm run dev
