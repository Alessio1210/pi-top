# 🎓 Pi-Top Face Recognition System

## Schulprojekt: Gesichtserkennung mit 30-Tage Datenspeicherung

Dieses System erkennt Personen in Echtzeit und speichert alle Erkennungen mit Timestamps in einer Supabase-Datenbank für 30 Tage.

---

## 📁 Projekt-Struktur

```
pi-top/
├── project_kamera.py              # Original (nur Head-Tracking)
├── project_kamera_v2.py           # NEU: Mit Face Recognition (WORK IN PROGRESS)
├── templates.py                   # HTML Templates
├── supabase_schema.sql            # Datenbank Schema
├── requirements.txt               # Python Dependencies
├── .env                           # Supabase Credentials
├── SETUP_GUIDE.md                 # Ausführliche Setup-Anleitung
└── download_cascade.sh            # Haar Cascade Download-Skript
```

---

## 🚀 Quick Start

### 1. Supabase einrichten

1. Öffne dein Supabase Dashboard
2. Gehe zu **SQL Editor**
3. Führe `supabase_schema.sql` aus
4. Erstelle Storage Buckets: `person-photos` und `detection-snapshots`
5. Setze Storage Policies (siehe SETUP_GUIDE.md)

### 2. Dependencies installieren

**Auf dem Mac:**
```bash
pip3 install -r requirements.txt
```

**Auf dem Pi-Top:**
```bash
# System-Dependencies
sudo apt-get update
sudo apt-get install -y cmake build-essential libopenblas-dev liblapack-dev

# Python Dependencies
pip3 install -r requirements.txt
```

**WICHTIG für Pi-Top:** Falls `dlib` Probleme macht:
```bash
sudo apt-get install python3-dlib
pip3 install face-recognition --no-deps
```

### 3. Server starten

**Aktuell (nur Head-Tracking):**
```bash
python3 project_kamera.py
```

**NEU (mit Face Recognition - COMING SOON):**
```bash
python3 project_kamera_v2.py
```

---

## 🎯 Features

### ✅ Bereits implementiert:
- [x] Automatische Kamera-Erkennung
- [x] Live-Video-Streaming
- [x] Head-Tracking mit Haar Cascade
- [x] Supabase Integration
- [x] Datenbank Schema mit 30-Tage Retention
- [x] Face Recognition Grundgerüst

### 🚧 In Arbeit:
- [ ] Enrollment-Seite (Person registrieren)
- [ ] Dashboard mit Statistiken
- [ ] Face Recognition API-Endpunkte
- [ ] Automatisches Foto-Upload zu Supabase Storage

### 📋 Geplant:
- [ ] Export von Statistiken (CSV/PDF)
- [ ] Email-Benachrichtigungen
- [ ] Multi-Kamera Support
- [ ] Mobile App

---

## 📊 Datenbank-Schema

### Tabellen:

**persons** - Registrierte Personen
- `id` (UUID)
- `name` (Text)
- `face_encoding` (JSONB)
- `photo_url` (Text)
- `notes` (Text)
- `created_at`, `updated_at` (Timestamps)

**detections** - Erkennungs-Historie
- `id` (UUID)
- `person_id` (Foreign Key)
- `detected_at` (Timestamp)
- `confidence` (Float)
- `snapshot_url` (Text, optional)
- `location` (Text)

### Views:

- `person_statistics` - Statistiken pro Person
- `daily_statistics` - Tägliche Zusammenfassung
- `recent_detections` - Letzte 100 Erkennungen

### Funktionen:

- `cleanup_old_detections()` - Löscht Daten älter als 30 Tage

---

## 🔧 Konfiguration

### .env Datei:

```env
SUPABASE_URL=https://csoooflqxcfbdxkiebyf.supabase.co
SUPABASE_KEY=dein_anon_key_hier
DETECTION_RETENTION_DAYS=30
DETECTION_CONFIDENCE_THRESHOLD=0.6
```

### Einstellungen anpassen:

- **Confidence Threshold**: Wie sicher muss die Erkennung sein? (0.0 - 1.0)
  - `0.4` = Sehr tolerant (mehr False Positives)
  - `0.6` = Ausgewogen (empfohlen)
  - `0.8` = Sehr streng (weniger Erkennungen)

- **Detection Cooldown**: Wie oft wird dieselbe Person in DB gespeichert?
  - Standard: 5 Sekunden
  - Anpassen in `project_kamera_v2.py`: `DETECTION_COOLDOWN_SECONDS`

---

## 📱 Verwendung

### Live-Stream ansehen:
```
http://192.168.0.45:8080/
```

### Person registrieren:
```
http://192.168.0.45:8080/enroll
```

1. Name eingeben
2. Foto aufnehmen (Gesicht muss sichtbar sein)
3. Optional: Notizen hinzufügen
4. Registrieren klicken

### Dashboard:
```
http://192.168.0.45:8080/dashboard
```

Zeigt:
- Anzahl registrierter Personen
- Erkennungen heute
- Verschiedene Personen heute
- Gesamt-Erkennungen (30 Tage)
- Liste aller Personen mit Statistiken
- Letzte Erkennungen

---

## 🛠️ Troubleshooting

### Problem: "No module named 'face_recognition'"

**Lösung:**
```bash
pip3 install face-recognition
```

Falls das fehlschlägt (auf Pi-Top):
```bash
sudo apt-get install python3-dlib
pip3 install face-recognition --no-deps
```

### Problem: "dlib installation failed"

**Lösung 1:** Verwende System-Package
```bash
sudo apt-get install python3-dlib
```

**Lösung 2:** Erhöhe Swap-Speicher
```bash
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Ändere CONF_SWAPSIZE=100 zu CONF_SWAPSIZE=1024
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
pip3 install dlib --no-cache-dir
```

### Problem: "No face detected" beim Enrollment

**Lösung:**
- Bessere Beleuchtung
- Direkt in die Kamera schauen
- Näher an die Kamera gehen
- Sonnenbrillen/Masken entfernen

### Problem: "Supabase connection failed"

**Lösung:**
- Prüfe `.env` Datei
- Prüfe Internetverbindung
- Prüfe RLS Policies in Supabase
- Prüfe ob Buckets erstellt sind

### Problem: Person wird nicht erkannt

**Lösung:**
- Confidence Threshold senken (in `.env`)
- Bessere Beleuchtung
- Mehr Trainingsfotos aus verschiedenen Winkeln
- Gesicht muss frontal zur Kamera sein

---

## 📈 Performance-Tipps

### Auf dem Pi-Top:

1. **Reduziere Auflösung** (in `project_kamera_v2.py`):
   ```python
   camera.set(cv2.CAP_PROP_FRAME_WIDTH, 320)  # Statt 640
   camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)  # Statt 480
   ```

2. **Erhöhe Frame-Skip** (nur jeden N-ten Frame verarbeiten):
   ```python
   if process_this_frame % 5 == 0:  # Statt % 3
   ```

3. **Reduziere Face Detection Größe**:
   ```python
   small_frame = cv2.resize(frame, (0, 0), fx=0.2, fy=0.2)  # Statt 0.25
   ```

---

## 🎓 Für das Schulprojekt

### Präsentations-Punkte:

1. **Technologie-Stack:**
   - Python + OpenCV + face_recognition
   - Flask Web-Framework
   - Supabase (PostgreSQL + Storage)
   - Raspberry Pi / Pi-Top

2. **Datenschutz:**
   - 30-Tage automatische Löschung
   - Gesichts-Encodings statt Fotos gespeichert
   - Lokale Verarbeitung (keine Cloud-AI)
   - DSGVO-konform

3. **Features:**
   - Echtzeit-Erkennung
   - Web-Interface
   - Statistiken & Reports
   - Automatische Datenverwaltung

4. **Herausforderungen:**
   - Performance auf Raspberry Pi
   - Beleuchtungs-Variationen
   - Genauigkeit vs. Geschwindigkeit
   - Datenschutz-Anforderungen

---

## 📝 Nächste Schritte

1. ✅ Supabase Schema erstellt
2. ✅ Dependencies definiert
3. ✅ Grundgerüst implementiert
4. 🚧 Enrollment-Seite fertigstellen
5. 🚧 Dashboard implementieren
6. 🚧 API-Endpunkte vervollständigen
7. ⏳ Testen auf Pi-Top
8. ⏳ Dokumentation vervollständigen

---

## 📞 Support

Bei Problemen:
1. Prüfe `SETUP_GUIDE.md`
2. Prüfe Troubleshooting-Sektion oben
3. Prüfe Supabase Logs
4. Prüfe Python Logs

---

## 📄 Lizenz

Schulprojekt - Nur für Bildungszwecke

---

**Viel Erfolg mit dem Projekt! 🎉**
