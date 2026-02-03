# Head-Tracking Setup für Pi-Top

## Problem
Das Head-Tracking funktioniert auf dem Pi-Top nicht, weil die Haar Cascade Datei nicht gefunden wird.

## Lösung

Das Skript `project_kamera.py` versucht jetzt automatisch:

1. ✅ **Automatische Suche** an vielen verschiedenen Orten
2. ✅ **System-Suche** mit dem `find` Kommando
3. ✅ **Automatischer Download** falls die Datei nicht gefunden wird

## Manueller Download (falls automatisch nicht funktioniert)

### Option 1: Bash-Skript verwenden
```bash
./download_cascade.sh
```

### Option 2: Manuell mit wget
```bash
wget https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml
```

### Option 3: Manuell mit curl
```bash
curl -O https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml
```

## Debugging

Wenn du das Skript startest, siehst du jetzt detaillierte Debug-Informationen:

```
🎯 Lade Head-Tracking Modell...
   OpenCV Version: 4.x.x
   📍 cv2.data verfügbar: /pfad/zur/datei
   🔍 Durchsuche 15 mögliche Pfade...
   ✓ Pfad 1 existiert: /usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml
   ✅ Haar Cascade erfolgreich geladen!
```

Diese Informationen helfen dir zu verstehen:
- Welche OpenCV-Version installiert ist
- Welche Pfade durchsucht werden
- Wo die Datei gefunden wurde (oder warum nicht)

## Häufige Probleme

### Problem: "cv2.data nicht verfügbar"
**Lösung:** Das ist normal bei älteren OpenCV-Versionen. Das Skript sucht automatisch an anderen Orten.

### Problem: "Haar Cascade nicht gefunden"
**Lösung:** Das Skript lädt die Datei automatisch herunter. Falls das fehlschlägt, verwende eine der manuellen Download-Optionen oben.

### Problem: Download schlägt fehl
**Lösung:** Prüfe deine Internetverbindung und stelle sicher, dass du Schreibrechte im Projektverzeichnis hast.

## Wo wird die Datei gespeichert?

Die heruntergeladene Datei wird im gleichen Verzeichnis wie `project_kamera.py` gespeichert:
```
/home/pi/Desktop/haarcascade_frontalface_default.xml
```

## Testen

Nach dem Setup kannst du testen, ob es funktioniert:

```bash
python3 project_kamera.py
```

Du solltest sehen:
```
✅ Haar Cascade erfolgreich geladen!
```

Dann öffne im Browser: `http://0.0.0.0:8080`

Das Head-Tracking sollte jetzt funktionieren! 🎯
