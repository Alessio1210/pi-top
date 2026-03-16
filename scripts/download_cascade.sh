#!/bin/bash
# Skript zum Herunterladen der Haar Cascade Datei für Gesichtserkennung

echo "🔽 Lade Haar Cascade Datei herunter..."

# Zielverzeichnis (im gleichen Ordner wie das Skript)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TARGET_FILE="$SCRIPT_DIR/haarcascade_frontalface_default.xml"

# URL der Datei
URL="https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"

# Prüfe ob die Datei bereits existiert
if [ -f "$TARGET_FILE" ]; then
    echo "✅ Datei existiert bereits: $TARGET_FILE"
    exit 0
fi

# Versuche mit wget
if command -v wget &> /dev/null; then
    echo "   Verwende wget..."
    wget -O "$TARGET_FILE" "$URL"
    if [ $? -eq 0 ]; then
        echo "✅ Download erfolgreich: $TARGET_FILE"
        exit 0
    fi
fi

# Versuche mit curl
if command -v curl &> /dev/null; then
    echo "   Verwende curl..."
    curl -o "$TARGET_FILE" "$URL"
    if [ $? -eq 0 ]; then
        echo "✅ Download erfolgreich: $TARGET_FILE"
        exit 0
    fi
fi

echo "❌ Fehler: Weder wget noch curl verfügbar!"
echo "   Bitte installiere eines der Tools:"
echo "   sudo apt-get install wget"
exit 1
