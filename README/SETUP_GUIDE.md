# 🎓 Face Recognition System - Setup Anleitung

## Schulprojekt: Gesichtserkennung mit 30-Tage Speicherung

---

## 📋 Schritt 1: Supabase Datenbank einrichten

### 1.1 SQL Schema ausführen

1. Gehe zu deinem Supabase Dashboard: https://supabase.com/dashboard
2. Wähle dein Projekt aus
3. Klicke auf **SQL Editor** (links in der Sidebar)
4. Klicke auf **New Query**
5. Kopiere den kompletten Inhalt von `supabase_schema.sql`
6. Füge ihn in den SQL Editor ein
7. Klicke auf **Run** (oder drücke Cmd/Ctrl + Enter)

✅ Du solltest sehen: "Success. No rows returned"

### 1.2 Storage Buckets erstellen

1. Klicke auf **Storage** (links in der Sidebar)
2. Klicke auf **Create a new bucket**

**Bucket 1: person-photos**

- Name: `person-photos`
- Public bucket: ✅ **JA** (aktivieren!)
- File size limit: 5 MB
- Allowed MIME types: `image/jpeg,image/png`

**Bucket 2: detection-snapshots**

- Name: `detection-snapshots`
- Public bucket: ✅ **JA** (aktivieren!)
- File size limit: 2 MB
- Allowed MIME types: `image/jpeg`

### 1.3 Storage Policies setzen

Für jeden Bucket:

1. Klicke auf den Bucket
2. Klicke auf **Policies**
3. Klicke auf **New Policy**
4. Wähle **For full customization**
5. Policy Name: `Public Access`
6. Allowed operations: Alle auswählen (SELECT, INSERT, UPDATE, DELETE)
7. Target roles: `anon`, `authenticated`
8. USING expression: `true`
9. WITH CHECK expression: `true`
10. Klicke auf **Save**

---

## 📦 Schritt 2: Python Dependencies installieren

### Auf deinem Mac (zum Testen):

```bash
cd /Users/alessiobetz/Documents/Programming/pi-top
pip3 install -r requirements.txt
```

### Auf dem Pi-Top:

**WICHTIG:** `dlib` braucht spezielle Installation auf Raspberry Pi!

```bash
# System-Dependencies installieren
sudo apt-get update
sudo apt-get install -y cmake build-essential libopenblas-dev liblapack-dev

# Python Dependencies
cd /home/pi/Desktop
pip3 install -r requirements.txt

# Falls dlib Probleme macht, verwende:
pip3 install dlib --no-cache-dir
```

**Alternative (wenn dlib nicht kompiliert):**

```bash
# Verwende vorcompilierte Version
sudo apt-get install python3-dlib
pip3 install face-recognition --no-deps
```

---

## 🚀 Schritt 3: Server starten

### Auf dem Mac (zum Testen):

```bash
python3 project_kamera.py
```

### Auf dem Pi-Top:

```bash
python3 project_kamera.py
```

Der Server startet auf: `http://0.0.0.0:8080`

---

## 🎯 Schritt 4: System verwenden

### 4.1 Neue Person registrieren

1. Öffne im Browser: `http://192.168.0.45:8080/enroll`
2. Gib den Namen der Person ein
3. Klicke auf **Foto aufnehmen**
4. Stelle sicher, dass das Gesicht gut sichtbar ist
5. Klicke auf **Person registrieren**

✅ Die Person ist jetzt im System!

### 4.2 Live-Erkennung

1. Öffne: `http://192.168.0.45:8080`
2. Gehe vor die Kamera
3. Du solltest deinen Namen neben deinem Gesicht sehen
4. Jede Erkennung wird automatisch in der Datenbank gespeichert

### 4.3 Dashboard & Statistiken

1. Öffne: `http://192.168.0.45:8080/dashboard`
2. Siehst du:
   - Alle registrierten Personen
   - Anzahl Erkennungen pro Person
   - Wann jemand zuletzt gesehen wurde
   - Tägliche Statistiken
   - Letzte Erkennungen

---

## 🔧 Troubleshooting

### Problem: "dlib installation failed"

**Lösung 1:** Verwende vorcompilierte Version

```bash
sudo apt-get install python3-dlib
```

**Lösung 2:** Kompiliere mit mehr Speicher

```bash
# Erhöhe Swap auf Pi
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Ändere CONF_SWAPSIZE=100 zu CONF_SWAPSIZE=1024
sudo dphys-swapfile setup
sudo dphys-swapfile swapon

# Dann installiere dlib
pip3 install dlib --no-cache-dir
```

### Problem: "No face detected"

**Lösung:**

- Stelle sicher, dass genug Licht vorhanden ist
- Schaue direkt in die Kamera
- Entferne Sonnenbrillen/Masken
- Gehe näher an die Kamera

### Problem: "Supabase connection failed"

**Lösung:**

- Prüfe `.env` Datei
- Stelle sicher, dass die Credentials korrekt sind
- Prüfe Internetverbindung
- Prüfe ob RLS Policies gesetzt sind

### Problem: "Person wird nicht erkannt"

**Lösung:**

- Confidence Threshold anpassen in `.env`
- Mehr Trainingsfotos von verschiedenen Winkeln
- Bessere Beleuchtung beim Enrollment

---

## 📊 Datenbank-Wartung

### Alte Daten manuell löschen (älter als 30 Tage)

Im Supabase SQL Editor:

```sql
SELECT cleanup_old_detections();
```

### Statistiken ansehen

```sql
-- Alle Personen mit Erkennungen
SELECT * FROM person_statistics ORDER BY total_detections DESC;

-- Tägliche Statistiken
SELECT * FROM daily_statistics;

-- Wer wurde heute gesehen?
SELECT p.name, COUNT(*) as times_seen
FROM detections d
JOIN persons p ON d.person_id = p.id
WHERE DATE(d.detected_at) = CURRENT_DATE
GROUP BY p.name;
```

---

## 🎓 Für das Schulprojekt

### Wichtige Features:

- ✅ 30-Tage Datenspeicherung (automatisch)
- ✅ Timestamps für jede Erkennung
- ✅ Statistiken und Reports
- ✅ Professionelle Datenbank-Struktur
- ✅ Web-Interface für Verwaltung

### Präsentations-Tipps:

1. Zeige das Dashboard mit Statistiken
2. Demonstriere Live-Erkennung
3. Erkläre die 30-Tage-Regel
4. Zeige die Supabase-Datenbank
5. Erkläre Privacy & Datenschutz

---

## 📝 Nächste Schritte

1. ✅ Supabase einrichten
2. ✅ Dependencies installieren
3. ✅ Server starten
4. ✅ Erste Person registrieren
5. ✅ Testen!
