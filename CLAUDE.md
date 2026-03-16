# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Face recognition security system for Pi-Top (Raspberry Pi educational device). Two Pis collaborate: Pi 1 runs camera + face recognition, Pi 2 runs access control (Zentrale). A React frontend displays live status.

## Commands

### Frontend
```bash
cd frontend
npm install
npm run dev        # Dev server at port 5173
npm run build      # Production build
npm run lint       # ESLint
```

### Backend
```bash
# Mac (development)
pip3 install -r requirements.txt
python3 backend/main.py       # Port 8000 (Pi 1 - face recognition)
python3 backend/zentrale.py   # Port 5001 (Pi 2 - access control)

# Pi-Top (production)
bash scripts/install_on_pi.sh   # Installs using system-site-packages venv
source venv/bin/activate
python3 backend/main.py
```

### Core C++
```bash
cd core
cmake . && make
# Or directly:
clang++ -O3 core/core_engine.cpp -o core_engine
```

### Database
Run `scripts/supabase_schema.sql` in Supabase SQL editor. Create storage buckets: `person-photos` and `detection-snapshots`.

## Architecture

### Two-Pi Distributed System

**Pi 1 (`backend/main.py`, port 8000)** — Camera, face recognition, hardware feedback
- Captures video, encodes faces, compares against Supabase `persons` table
- Spawns `core/core_engine` subprocess for I2C hardware (LCD, RGB backlight, keypad)
- Controls buzzer/LEDs via `pitop` SDK
- If unknown face detected, POSTs to Zentrale and polls for decision
- Streams MJPEG video at `/video_feed`; pushes SSE events at `/api/events`

**Pi 2 (`backend/zentrale.py`, port 5001)** — Access authorization
- Receives access requests from Pi 1
- Waits for physical button press (D0=accept, D1=reject) or console input
- Returns decision via `/api/access_status`; Pi 1 polls this endpoint

**Frontend (`frontend/src/App.tsx`)** — Web dashboard
- Connects to Pi 1's SSE stream for live detection events
- Displays video feed, statistics, and detection history

**Core C++ (`core/core_engine.cpp`)** — I2C/UART hardware layer
- Manages LCD display (Grove/PCF8574), RGB backlight, UART keypad
- Called as subprocess by `main.py` with command-line args

### Data Flow
1. Camera → face_recognition → compare encodings from Supabase
2. Known face: grant access, log detection, show on LCD
3. Unknown face: request authorization from Zentrale
4. Zentrale decision → returned to Pi 1 → hardware feedback (buzzer, LED, LCD)
5. All detections stored in Supabase; alerts sent via Telegram/Discord webhooks

### Key Config
- `.env` at project root: `SUPABASE_URL`, `SUPABASE_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DISCORD_WEBHOOK_URL`, `ZENTRALE_URL`, `DETECTION_CONFIDENCE_THRESHOLD` (default 0.6), `DETECTION_RETENTION_DAYS` (default 30)
- Pi-specific: uses `system-site-packages` venv to avoid recompiling dlib/opencv

### Supabase Schema
- `persons`: name, face_encoding (JSONB), photo_url, pin
- `detections`: person_id, detected_at, confidence
- `access_logs`: person_id, status (accepted/rejected/timeout), timestamp
- Auto-cleanup via `cleanup_old_detections()` for 30-day retention
