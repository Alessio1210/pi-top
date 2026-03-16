# 🎥 Pi-Top Kamera-Server

Ein Flask-basierter Webserver für Live-Streaming von USB-Kameras auf dem Pi-Top.

## 📋 Features

- ✅ **Automatische Kamera-Erkennung** - Findet automatisch die erste verfügbare USB-Kamera
- 🎥 **Live-Stream** - MJPEG-Stream im Browser
- 📸 **Snapshot-Funktion** - Speichere Einzelbilder direkt im Browser
- ⛶ **Vollbild-Modus** - Für bessere Ansicht
- 📊 **Status-API** - REST-API für Kamera-Informationen
- 🎨 **Moderne UI** - Responsive Design mit Gradients und Animationen
- ⌨️ **Tastatur-Shortcuts** - Schnelle Steuerung

## 🔌 Hardware

### Angeschlossene Komponenten:
- **USB-Kamera** (schwarz) → USB-Port
- **LCD-Display**
- **Ampel-LED**
- **Zwei-Buttons**
- **Keypad**


## 🚀 Installation auf dem Pi-Top

### 1. Dateien übertragen

Kopiere die Datei `project_kamera.py` auf deinen Pi-Top:

```bash
# Von deinem Mac aus (im Terminal):
scp project_kamera.py pi@<PI-TOP-IP>:~/
```

Oder nutze einen USB-Stick oder GitHub.

### 2. Abhängigkeiten installieren

Auf dem Pi-Top:

```bash
# Virtuelles Environment erstellen (empfohlen)
python3 -m venv venv
source venv/bin/activate

# Pakete installieren
pip install flask opencv-python
```

**Alternative ohne venv:**
```bash
pip3 install --user flask opencv-python
```

### 3. Server starten

```bash
# Mit venv:
source venv/bin/activate
python project_kamera.py

# Ohne venv:
python3 project_kamera.py
```

## 🌐 Zugriff auf den Stream

### Auf dem Pi-Top selbst:
```
http://localhost:8080
```

### Von anderen Geräten im Netzwerk:
```
http://<PI-TOP-IP-ADRESSE>:8080
```

Die IP-Adresse des Pi-Top findest du mit:
```bash
hostname -I
```

## 🎮 Bedienung

### Im Browser:

**Buttons:**
- 🔄 **Neu laden** - Seite aktualisieren
- ⛶ **Vollbild** - Vollbildmodus aktivieren
- 📸 **Snapshot** - Aktuelles Bild speichern

**Tastatur-Shortcuts:**
- `F` - Vollbild umschalten
- `S` - Snapshot erstellen
- `R` - Seite neu laden

## 📡 API-Endpunkte

### Status abfragen:
```bash
curl http://localhost:8080/status
```

**Antwort:**
```json
{
  "status": "active",
  "camera_index": 0,
  "width": 640,
  "height": 480,
  "fps": 30,
  "backend": "V4L2"
}
```

### Video-Stream direkt:
```
http://localhost:8080/video_feed
```

## 🔧 Konfiguration

Die Kamera-Einstellungen können in der Datei `project_kamera.py` angepasst werden:

```python
# Zeile ~75-77
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)   # Breite
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)  # Höhe
camera.set(cv2.CAP_PROP_FPS, 30)            # Frames pro Sekunde
```

Port ändern (Standard: 8080):
```python
# Zeile ~461
app.run(host='0.0.0.0', port=8080, ...)
```

## 🐛 Troubleshooting

### Kamera wird nicht gefunden
```bash
# Verfügbare Kameras anzeigen
ls /dev/video*

# Kamera-Berechtigungen prüfen
sudo usermod -a -G video $USER
# Danach neu anmelden!
```

### Port bereits belegt
Ändere den Port in `project_kamera.py` oder stoppe den anderen Dienst:
```bash
# Prozess auf Port 8080 finden
sudo lsof -i :8080

# Prozess beenden
sudo kill <PID>
```

### Schlechte Performance
- Reduziere die Auflösung (z.B. 320x240)
- Reduziere die FPS (z.B. 15)
- Reduziere die JPEG-Qualität (Zeile ~109: `cv2.IMWRITE_JPEG_QUALITY, 85` → `70`)

## 🔄 Autostart einrichten (optional)

### Mit systemd:

1. Service-Datei erstellen:
```bash
sudo nano /etc/systemd/system/pitop-camera.service
```

2. Inhalt:
```ini
[Unit]
Description=Pi-Top Kamera-Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
ExecStart=/home/pi/venv/bin/python /home/pi/project_kamera.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

3. Service aktivieren:
```bash
sudo systemctl daemon-reload
sudo systemctl enable pitop-camera.service
sudo systemctl start pitop-camera.service
```

4. Status prüfen:
```bash
sudo systemctl status pitop-camera.service
```

## 📝 Projekt-Struktur

```
pi-top/
├── project_kamera.py          # 🎯 Haupt-Server (DIESES SCRIPT)
├── camera_server.py           # Alt (mit pitop-Library)
├── camera_server_simple.py    # Alt (Test-Version)
├── lamp.py                    # LED Jingle Bells Projekt
├── notizen.md                 # Hardware-Notizen
└── README.md                  # Diese Anleitung
```

## 🎯 Nächste Schritte

- [ ] Mikrofon-Integration (Audio-Level anzeigen)
- [ ] Aufnahme-Funktion (Video speichern)
- [ ] Motion-Detection (Bewegungserkennung)
- [ ] Mehrere Kameras gleichzeitig
- [ ] Authentifizierung (Login)

## 📞 Support

Bei Problemen:
1. Prüfe die Konsolen-Ausgabe des Servers
2. Teste die Kamera mit: `python3 -c "import cv2; print(cv2.VideoCapture(0).read())"`
3. Prüfe die Browser-Konsole (F12)

---

**Viel Erfolg mit deinem Pi-Top Kamera-Server! 🚀**
