#!/bin/bash
# Dev-Modus: Pi1 + Pi2 auf einem einzigen Pi
cd "$(dirname "$0")/.."

# Zentrale_URL auf localhost setzen (beide laufen lokal)
export ZENTRALE_URL=http://localhost:5001

source venv/bin/activate

echo "▶ Starte Zentrale (Pi2) auf Port 5001..."
python3 backend/zentrale.py &
ZENTRALE_PID=$!

sleep 2

echo "▶ Starte Kamera-Backend (Pi1) auf Port 8000..."
python3 backend/main.py &
BACKEND_PID=$!

sleep 2

echo "▶ Starte Frontend auf Port 5173..."
cd frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Alles läuft:"
echo "   Frontend  → http://$(hostname -I | awk '{print $1}'):5173"
echo "   Backend   → http://$(hostname -I | awk '{print $1}'):8000"
echo "   Zentrale  → http://$(hostname -I | awk '{print $1}'):5001"
echo ""
echo "Stoppen mit Ctrl+C"

# Alle Prozesse beenden wenn Ctrl+C
trap "kill $ZENTRALE_PID $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
