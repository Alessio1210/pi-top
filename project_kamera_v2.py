#!/usr/bin/env python3
"""
Pi-Top Face Recognition System mit Supabase
Schulprojekt: 30-Tage Speicherung mit Timestamps
"""

from flask import Flask, Response, render_template_string, request, jsonify, send_from_directory
import cv2
import face_recognition
import numpy as np
import threading
import sys
import os
import time
import json
import base64
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image
import uuid

import requests
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
SERVER_PORT = 8000  # Port Konfiguration (Standard HTTP Alternativ-Port)

# Supabase Client
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Telegram Bot Konfiguration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
telegram_alert_cooldown = datetime.min
unknown_face_counter = 0
UNKNOWN_THRESHOLD = 15  # Ca. 2-3 Sekunden durchgehend unbekannt vor Alarm

# Globale Variablen
camera = None
camera_lock = threading.Lock()
processing_lock = threading.Lock() # Lock für Face Recognition (verhindert Segfaults)
camera_info = {
    'index': -1,
    'width': 0,
    'height': 0,
    'fps': 0,
    'backend': 'Unknown'
}

# Face Recognition Einstellungen
face_recognition_enabled = True
known_face_encodings = []
known_face_names = []
known_face_ids = []
last_detection_time = {}  # Verhindert Spam in DB

# Async AI Variablen
ai_frame_buffer = None
ai_frame_lock = threading.Lock()
ai_results = [] # [(top, right, bottom, left), (name, label)]
ai_results_lock = threading.Lock()
is_running = True

# Detection Settings
DETECTION_CONFIDENCE_THRESHOLD = float(os.getenv('DETECTION_CONFIDENCE_THRESHOLD', 0.6))
DETECTION_COOLDOWN_SECONDS = 5  # Nur alle 5 Sekunden in DB speichern

# Statistiken
stats = {
    'total_detections_today': 0,
    'unique_persons_today': set(),
    'last_cleanup': datetime.now()
}

# Globale Variable für aktuellen Frame (für Snapshots)
current_frame = None

# Temporärer Speicher für Enrollment
enrollment_cache = {}

def load_known_faces():
    """
    Lädt alle bekannten Gesichter aus Supabase
    """
    global known_face_encodings, known_face_names, known_face_ids
    
    print("\n👤 Lade bekannte Gesichter aus Supabase...")
    
    try:
        # Hole alle Personen aus der Datenbank
        response = supabase.table('persons').select('*').execute()
        
        if not response.data:
            print("   ℹ️  Keine Personen in der Datenbank")
            return
        
        known_face_encodings = []
        known_face_names = []
        known_face_ids = []
        
        for person in response.data:
            # Face Encoding aus JSONB laden
            encoding = np.array(person['face_encoding'])
            
            known_face_encodings.append(encoding)
            known_face_names.append(person['name'])
            known_face_ids.append(person['id'])
        
        print(f"   ✅ {len(known_face_names)} Personen geladen: {', '.join(known_face_names)}")
        # Debug IDs
        print(f"   🆔 IDs: {known_face_ids}")
        
    except Exception as e:
        print(f"   ❌ Fehler beim Laden der Gesichter: {e}")

def save_detection(person_id, person_name, confidence):
    """
    Speichert eine Erkennung in Supabase (mit Cooldown)
    """
    global last_detection_time, stats
    
    # Cooldown Check
    now = datetime.now()
    last_time = last_detection_time.get(person_id)
    
    if last_time and (now - last_time).total_seconds() < DETECTION_COOLDOWN_SECONDS:
        return  # Zu früh, nicht speichern
    
    try:
        # Speichere in Datenbank
        detection_data = {
            'person_id': person_id,
            'confidence': float(confidence),
            'detected_at': now.isoformat(),
            'location': 'Pi-Top Camera'
        }
        
        response = supabase.table('detections').insert(detection_data).execute()
        
        # Update cooldown
        last_detection_time[person_id] = now
        
        # Update Stats
        stats['total_detections_today'] += 1
        stats['unique_persons_today'].add(person_name)
        
        print(f"   💾 Erkennung gespeichert: {person_name} ({confidence:.2%}) -> DB ID: {response.data[0]['id'] if response.data else 'Unbekannt'}")
        
    except Exception as e:
        print(f"   ❌ Fehler beim Speichern der Detection in DB: {e}")
        # Debug info
        print(f"      Person ID: {person_id}, Name: {person_name}")

def cleanup_old_detections():
    """
    Löscht Detections älter als 30 Tage
    """
    global stats
    
    # Nur einmal pro Tag ausführen
    if (datetime.now() - stats['last_cleanup']).days < 1:
        return
    
    try:
        print("\n🧹 Cleanup: Lösche alte Detections...")
        
        # Rufe Supabase Funktion auf
        result = supabase.rpc('cleanup_old_detections').execute()
        
        deleted_count = result.data if result.data else 0
        print(f"   ✅ {deleted_count} alte Einträge gelöscht")
        
        stats['last_cleanup'] = datetime.now()
        
    except Exception as e:
        print(f"   ❌ Cleanup Fehler: {e}")


def send_telegram_alert_thread(image_bytes):
    """
    Sendet das Bild im Hintergrund an Telegram
    """
    token = TELEGRAM_BOT_TOKEN
    chat_id = TELEGRAM_CHAT_ID
    
    if not token or not chat_id:
        print("   ❌ Telegram Token oder Chat ID fehlt!")
        return

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    
    try:
        files = {'photo': ('alert.jpg', image_bytes, 'image/jpeg')}
        data = {'chat_id': chat_id, 'caption': '🚨 <b>ALARM: Unbekannte Person erkannt!</b>\nVersuchter Zugriff.', 'parse_mode': 'HTML'}
        
        response = requests.post(url, files=files, data=data, timeout=10)
        
        if response.status_code == 200:
            print("   ✅ Telegram Alarm gesendet!")
        else:
            print(f"   ❌ Telegram Fehler: {response.text}")
    except Exception as e:
        print(f"   ❌ Konnte Telegram nicht erreichen: {e}")

def trigger_alert(frame):
    """
    Startet den Alarm-Prozess
    """
    global telegram_alert_cooldown
    
    # Cooldown Check (z.B. nur alle 60 Sekunden Alarm)
    if datetime.now() < telegram_alert_cooldown:
        return

    # Bild konvertieren
    ret, buffer = cv2.imencode('.jpg', frame)
    if ret:
        print("\n🚨 UNBEKANNTE PERSON - Sende Alarm...")
        telegram_alert_cooldown = datetime.now() + timedelta(seconds=60)
        
        # In separatem Thread senden (damit Video nicht stockt)
        t = threading.Thread(target=send_telegram_alert_thread, args=(buffer.tobytes(),))
        t.start()

def ai_worker_thread():
    """
    Hintergrund-Thread für Face Recognition
    """
    global ai_frame_buffer, ai_results, unknown_face_counter
    
    print("🤖 AI Worker gestartet...")
    
    while is_running:
        # Hole neuesten Frame
        frame_to_process = None
        with ai_frame_lock:
            if ai_frame_buffer is not None:
                frame_to_process = ai_frame_buffer.copy()
        
        if frame_to_process is None:
            time.sleep(0.01)
            continue

        try:
            # Resize für schnellere Verarbeitung (0.5 für mehr Genauigkeit)
            scale_factor = 0.5
            inverse_scale = int(1/scale_factor)
            
            small_frame = cv2.resize(frame_to_process, (0, 0), fx=scale_factor, fy=scale_factor)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            
            # Finde Gesichter
            # Hier brauchen wir keinen Lock mehr, da wir im eigenen Thread sind
            current_locations = face_recognition.face_locations(rgb_small_frame)
            current_encodings = face_recognition.face_encodings(rgb_small_frame, current_locations)
            
            new_results = []
            current_face_names_for_alert = []
            
            for face_encoding, location in zip(current_encodings, current_locations):
                # Vergleiche mit bekannten Gesichtern
                name = "Unbekannt"
                confidence = 0.0
                person_id = None
                label_text = "Unbekannt"
                
                if len(known_face_encodings) > 0:
                    # Berechne Distanzen
                    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                    best_match_index = np.argmin(face_distances)
                    
                    # Confidence = 1 - distance
                    confidence = 1 - face_distances[best_match_index]
                    
                    if confidence > DETECTION_CONFIDENCE_THRESHOLD:
                        name = known_face_names[best_match_index]
                        person_id = known_face_ids[best_match_index]
                        label_text = f"{name} ({confidence:.0%})"
                        
                        # Speichere Detection in DB
                        save_detection(person_id, name, confidence)
                
                # Skaliere Koordinaten zurück
                top, right, bottom, left = location
                top *= inverse_scale
                right *= inverse_scale
                bottom *= inverse_scale
                left *= inverse_scale
                
                new_results.append(((top, right, bottom, left), (name, label_text)))
                current_face_names_for_alert.append(name)
            
            # Ergebnisse update
            with ai_results_lock:
                ai_results = new_results
                
            # === Alarm Logik ===
            has_known = any(n != "Unbekannt" for n in current_face_names_for_alert)
            has_unknown = any(n == "Unbekannt" for n in current_face_names_for_alert)
            
            if has_known:
                unknown_face_counter = 0
            elif has_unknown:
                unknown_face_counter += 1
                if unknown_face_counter >= UNKNOWN_THRESHOLD:
                    trigger_alert(frame_to_process)
                    unknown_face_counter = 0
            else:
                 # Kein Gesicht -> Zähler langsam abbauen oder resetten?
                 # Resetten ist sicherer
                 if unknown_face_counter > 0:
                     unknown_face_counter -= 1

        except Exception as e:
            print(f"⚠️ AI Thread Fehler: {e}")
            
        # Kurze Pause um CPU zu schonen
        time.sleep(0.01)


def find_camera():
    """
    Sucht automatisch nach verfügbaren Kameras
    """
    print("🔍 Suche nach verfügbaren Kameras...")
    
    for index in range(6):
        print(f"   Teste Kamera-Index {index}...", end=" ")
        
        test_cam = cv2.VideoCapture(index)
        
        if test_cam.isOpened():
            ret, frame = test_cam.read()
            if ret and frame is not None:
                width = int(test_cam.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(test_cam.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = int(test_cam.get(cv2.CAP_PROP_FPS))
                backend = test_cam.getBackendName()
                
                print(f"✅ Gefunden! ({width}x{height} @ {fps}fps, Backend: {backend})")
                
                camera_info['index'] = index
                camera_info['width'] = width
                camera_info['height'] = height
                camera_info['fps'] = fps if fps > 0 else 30
                camera_info['backend'] = backend
                
                return test_cam
            else:
                test_cam.release()
                print("❌ Kein Frame")
        else:
            print("❌ Nicht verfügbar")
    
    print("\n❌ Keine funktionierende Kamera gefunden!")
    return None

def initialize_camera():
    """
    Initialisiert die Kamera
    """
    global camera
    
    camera = find_camera()
    
    if camera is None:
        print("\n⚠️  WARNUNG: Keine Kamera gefunden!")
        return False
    
    print("\n⚙️  Konfiguriere Kamera-Einstellungen...")
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_FPS, 60) # Versuch auf 60 FPS zu setzen
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    camera_info['width'] = int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))
    camera_info['height'] = int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
    camera_info['fps'] = int(camera.get(cv2.CAP_PROP_FPS))
    
    print(f"   ✅ Auflösung: {camera_info['width']}x{camera_info['height']}")
    print(f"   ✅ FPS: {camera_info['fps']}")
    print(f"   ✅ Backend: {camera_info['backend']}")
    
    return True

def generate_frames():
    """
    Generator für Video-Streaming mit Face Recognition
    """
    # Generator für Video-Streaming (Hochoptimiert für FPS)
    global camera, current_frame, ai_frame_buffer
    
    if camera is None:
        yield b'--frame\r\nContent-Type: text/plain\r\n\r\nKeine Kamera verfuegbar\r\n'
        return
    
    while True:
        with camera_lock:
            success, frame = camera.read()
            
            if not success:
                print("⚠️ Fehler beim Lesen des Kamera-Frames")
                break
            
            # 1. Update Globals (für Enrollment & AI)
            current_frame = frame  # Referenz (schnell)
            
            # Sende an AI Thread (nur Copy wenn nötig, hier Referenz ok da AI copy macht)
            with ai_frame_lock:
                ai_frame_buffer = frame
            
            # 2. Hole letzte AI Ergebnisse (ohne zu warten!)
            current_results = []
            with ai_results_lock:
                current_results = ai_results # Copy reference
            
            # 3. Zeichne Ergebnisse
            for (top, right, bottom, left), (name, label_text) in current_results:
                color = (0, 255, 0) if name != "Unbekannt" else (0, 0, 255)
                thickness = 3
                
                # Box Design
                cv2.rectangle(frame, (left, top), (right, bottom), color, thickness)
                corner_len = 20
                cv2.line(frame, (left, top), (left + corner_len, top), color, 4)
                cv2.line(frame, (left, top), (left, top + corner_len), color, 4)
                cv2.line(frame, (right, top), (right - corner_len, top), color, 4)
                cv2.line(frame, (right, top), (right, top + corner_len), color, 4)
                cv2.line(frame, (left, bottom), (left + corner_len, bottom), color, 4)
                cv2.line(frame, (left, bottom), (left, bottom - corner_len), color, 4)
                cv2.line(frame, (right, bottom), (right - corner_len, bottom), color, 4)
                cv2.line(frame, (right, bottom), (right, bottom - corner_len), color, 4)
                
                # Text
                (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                cv2.rectangle(frame, (left, top - th - 10), (left + tw + 10, top), color, -1)
                cv2.putText(frame, label_text, (left + 5, top - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
            
            # 4. Kodieren & Senden (High Speed)
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75]) # 75% Quality für Speed
            
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# ============================================================
# FLASK ROUTES
# ============================================================

@app.route('/')
def index():
    """
    Haupt-Seite mit Live-Stream
    """
    html = """
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pi-Top Face Recognition</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 20px;
            }
            
            h1 {
                color: white;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
                margin: 30px 0;
                font-size: 2.5em;
                text-align: center;
            }
            
            .container {
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                padding: 30px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 900px;
                width: 100%;
            }
            
            .video-container {
                position: relative;
                border-radius: 15px;
                overflow: hidden;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                background: #000;
                aspect-ratio: 4/3;
            }
            
            .video-container img {
                width: 100%;
                height: 100%;
                object-fit: cover;
                display: block;
            }
            
            .info {
                margin-top: 20px;
                padding: 15px;
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                border-radius: 10px;
                color: white;
                text-align: center;
                font-weight: 500;
            }
            
            .controls {
                margin-top: 20px;
                display: flex;
                gap: 10px;
                justify-content: center;
                flex-wrap: wrap;
            }

            .cam-status {
                margin-top: 10px;
                padding: 8px 15px;
                border-radius: 20px;
                font-weight: bold;
                display: inline-block;
                text-align: center;
            }
            .cam-status.on { background: #c6f6d5; color: #2f855a; border: 1px solid #2f855a; }
            .cam-status.off { background: #fed7d7; color: #c53030; border: 1px solid #c53030; }
            
            button, .btn {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                text-decoration: none;
                display: inline-block;
            }
            
            button:hover, .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(0,0,0,0.3);
            }
            
            .stats {
                margin-top: 15px;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 10px;
            }
            
            .stat-item {
                background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
                padding: 10px;
                border-radius: 8px;
                text-align: center;
            }
            
            .stat-label {
                font-size: 12px;
                color: #666;
                font-weight: 600;
                text-transform: uppercase;
            }
            
            .stat-value {
                font-size: 18px;
                color: #333;
                font-weight: bold;
                margin-top: 5px;
            }
        </style>
    </head>
    <body>
        <h1>🎯 Pi-Top Face Recognition</h1>
        
        <div class="container">
            <div class="video-container">
                <img id="videoStream" src="{{ url_for('video_feed') }}" alt="Kamera Stream">
            </div>
            
            <div style="text-align: center; margin-top: 15px;">
                {% if camera_status %}
                <span class="cam-status on">📷 Connection: ON</span>
                {% else %}
                <span class="cam-status off">📷 Connection: OFF</span>
                {% endif %}
            </div>
            
            <div class="info">
                <strong>Live Face Recognition aktiv</strong>
            </div>
            
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-label">Registrierte Personen</div>
                    <div class="stat-value" id="totalPersons">{{ total_persons }}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Erkennungen Heute</div>
                    <div class="stat-value" id="detectionsToday">{{ detections_today }}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Confidence</div>
                    <div class="stat-value">{{ (confidence_threshold * 100)|int }}%</div>
                </div>
            </div>
            
            <div class="controls">
                <a href="/enroll" class="btn">➕ Person registrieren</a>
                <a href="/dashboard" class="btn">📊 Dashboard</a>
                <button onclick="location.reload()">🔄 Neu laden</button>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Hole Statistiken
    try:
        persons_count = len(known_face_names)
        detections_today = stats['total_detections_today']
    except:
        persons_count = 0
        detections_today = 0
    
    # Kamera Status prüfen
    camera_active = False
    if camera is not None:
        if isinstance(camera, cv2.VideoCapture):
            camera_active = camera.isOpened()
    
    return render_template_string(
        html,
        total_persons=persons_count,
        detections_today=detections_today,
        confidence_threshold=DETECTION_CONFIDENCE_THRESHOLD,
        camera_status=camera_active
    )

@app.route('/video_feed')
def video_feed():
    """
    Video-Stream Route
    """
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/enroll')
def enroll_page():
    """
    Enrollment-Seite für neue Personen
    """
    html = """
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Person Registrieren - Pi-Top</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 20px;
                color: #333;
            }
            .container {
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                padding: 30px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 800px;
                width: 100%;
            }
            h1 { text-align: center; color: #4a5568; margin-bottom: 20px; }
            .grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
            }
            @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
            
            .video-box {
                background: #000;
                border-radius: 10px;
                overflow: hidden;
                aspect-ratio: 4/3;
            }
            .video-box img { width: 100%; height: 100%; object-fit: cover; }
            
            .form-box { padding: 10px; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; font-weight: 600; }
            input, textarea {
                width: 100%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 5px;
                font-size: 16px;
            }
            
            .btn {
                width: 100%;
                padding: 12px;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
                transition: transform 0.2s;
            }
            .btn-capture { background: #4299e1; color: white; margin-bottom: 10px; }
            .btn-save { background: #48bb78; color: white; }
            .btn-back { background: #a0aec0; color: white; margin-top: 10px; text-decoration: none; display: block; text-align: center; }
            
            .btn:hover { transform: translateY(-2px); opacity: 0.9; }
            
            #previewImage {
                display: none;
                width: 100%;
                border-radius: 10px;
                margin-bottom: 15px;
                border: 3px solid #48bb78;
            }
            
            .status { margin-top: 10px; padding: 10px; border-radius: 5px; text-align: center; display: none; }
            .status.success { background: #c6f6d5; color: #2f855a; }
            .status.error { background: #fed7d7; color: #c53030; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>👤 Neue Person Registrieren</h1>
            
            <div class="grid">
                <div>
                    <div class="video-box">
                        <img id="liveVideo" src="{{ url_for('video_feed') }}" alt="Live Stream">
                        <img id="previewImage" alt="Snapshot">
                    </div>
                    <div style="margin-top: 10px; text-align: center;">
                        <button onclick="captureFace()" class="btn btn-capture">📷 Gesicht erfassen</button>
                    </div>
                </div>
                
                <div class="form-box">
                    <div class="form-group">
                        <label>Name *</label>
                        <input type="text" id="name" placeholder="Vorname Nachname" required>
                    </div>
                    
                    <div class="form-group">
                        <label>Mitarbeiternummer</label>
                        <input type="text" id="employee_id" placeholder="z.B. MA-12345">
                    </div>
                    
                    <div class="form-group">
                        <label>Notizen</label>
                        <textarea id="notes" rows="3" placeholder="Abteilung, Position, etc."></textarea>
                    </div>
                    
                    <button onclick="savePerson()" class="btn btn-save" id="saveBtn" disabled>💾 Speichern</button>
                    <a href="/" class="btn btn-back">Zurück zur Übersicht</a>
                    
                    <div id="statusMessage" class="status"></div>
                </div>
            </div>
        </div>
        
        <script>
            let capturedData = null;
            
            async function captureFace() {
                const status = document.getElementById('statusMessage');
                status.style.display = 'none';
                
                try {
                    const response = await fetch('/api/capture_face', { method: 'POST' });
                    const data = await response.json();
                    
                    if (data.success) {
                        capturedData = data;
                        
                        // Show preview
                        const liveVideo = document.getElementById('liveVideo');
                        const preview = document.getElementById('previewImage');
                        
                        preview.src = 'data:image/jpeg;base64,' + data.image;
                        liveVideo.style.display = 'none';
                        preview.style.display = 'block';
                        
                        // Enable save
                        document.getElementById('saveBtn').disabled = false;
                        
                        showMessage('Gesicht erfolgreich erfasst!', 'success');
                    } else {
                        showMessage(data.error || 'Fehler beim Erfassen', 'error');
                    }
                } catch (e) {
                    showMessage('Verbindungsfehler: ' + e.message, 'error');
                }
            }
            
            async function savePerson() {
                if (!capturedData) return;
                
                const name = document.getElementById('name').value;
                const employeeId = document.getElementById('employee_id').value;
                const notes = document.getElementById('notes').value;
                
                if (!name) {
                    showMessage('Bitte einen Namen eingeben', 'error');
                    return;
                }
                
                const status = document.getElementById('statusMessage');
                status.innerHTML = 'Speichere...';
                status.className = 'status';
                status.style.display = 'block';
                
                try {
                    const payload = {
                        capture_id: capturedData.capture_id,
                        name: name,
                        employee_number: employeeId,
                        notes: notes
                    };
                    
                    const response = await fetch('/api/register_person', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        showMessage('✅ Person erfolgreich gespeichert!', 'success');
                        setTimeout(() => window.location.href = '/', 2000);
                    } else {
                        showMessage('❌ Fehler: ' + result.error, 'error');
                    }
                } catch (e) {
                    showMessage('❌ Fehler: ' + e.message, 'error');
                }
            }
            
            function showMessage(msg, type) {
                const el = document.getElementById('statusMessage');
                el.innerText = msg;
                el.className = 'status ' + type;
                el.style.display = 'block';
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/api/capture_face', methods=['POST'])
def capture_face_api():
    """
    Erfasst ein Gesicht aus dem aktuellen Frame
    """
    global current_frame, enrollment_cache
    
    if current_frame is None:
        return jsonify({'success': False, 'error': 'Kein Kamerabild verfügbar'})
    
    try:
        # Kopie des Frames
        frame = current_frame.copy()
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Suche Gesichter
        with processing_lock:
            face_locations = face_recognition.face_locations(rgb_frame)
        
        if len(face_locations) == 0:
            return jsonify({'success': False, 'error': 'Kein Gesicht erkannt'})
        
        if len(face_locations) > 1:
            return jsonify({'success': False, 'error': 'Zu viele Gesichter erkannt (Bitte nur eine Person)'})
            
        # Encoding berechnen
        with processing_lock:
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        if not face_encodings:
            return jsonify({'success': False, 'error': 'Konnte Gesichtszüge nicht extrahieren'})
            
        encoding = face_encodings[0]
        
        # Crop Face für Preview
        top, right, bottom, left = face_locations[0]
        # Etwas Rand hinzufügen
        h, w, _ = frame.shape
        top = max(0, top - 50)
        bottom = min(h, bottom + 50)
        left = max(0, left - 50)
        right = min(w, right + 50)
        
        face_image = frame[top:bottom, left:right]
        
        # Encode image to base64
        success, buffer = cv2.imencode('.jpg', face_image)
        if not success:
            return jsonify({'success': False, 'error': 'Bildfehler'})
            
        img_str = base64.b64encode(buffer).decode('utf-8')
        
        # Cache Encoding
        capture_id = str(uuid.uuid4())
        enrollment_cache[capture_id] = {
            'encoding': encoding.tolist(),
            'timestamp': datetime.now()
        }
        
        return jsonify({
            'success': True,
            'capture_id': capture_id,
            'image': img_str
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/register_person', methods=['POST'])
def register_person_api():
    """
    Speichert eine neue Person in der Datenbank
    """
    global enrollment_cache
    
    data = request.json
    capture_id = data.get('capture_id')
    name = data.get('name')
    employee_number = data.get('employee_number')
    notes = data.get('notes')
    
    if not capture_id or capture_id not in enrollment_cache:
        return jsonify({'success': False, 'error': 'Capture ID ungültig oder abgelaufen'})
        
    if not name:
        return jsonify({'success': False, 'error': 'Name fehlt'})
    
    try:
        encoding_data = enrollment_cache.pop(capture_id)
        
        # Daten für DB vorbereiten
        person_data = {
            'name': name,
            'face_encoding': encoding_data['encoding'],
            'notes': notes
        }
        
        if employee_number:
            # Versuche employee_number zu speichern
            # Fallback: Wenn Spalte nicht existiert, in Notes speichern
            person_data['employee_number'] = employee_number
            
        try:
            print(f"   💾 Versuche Person zu speichern: {person_data}")
            response = supabase.table('persons').insert(person_data).execute()
            print(f"   ✅ DB Response: {response}")
        except Exception as db_err:
            print(f"   ⚠️ DB Fehler (Erster Versuch): {db_err}")
            error_msg = str(db_err).lower()
            if "employee_number" in error_msg and "column" in error_msg:
                # Spalte existiert nicht, speichere in Notes
                print("   ⚠️ Spalte 'employee_number' existiert nicht. Speichere in Notes.")
                person_data.pop('employee_number')
                person_data['notes'] = f"{notes or ''} [ID: {employee_number}]".strip()
                supabase.table('persons').insert(person_data).execute()
            else:
                raise db_err
        
        print(f"✅ Neue Person erfolgreich registriert: {name} (ID: {employee_number})")
        
        # Gesichter neu laden
        load_known_faces()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"❌ Fehler bei Registrierung: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/dashboard')
def dashboard():
    """
    Dashboard mit Statistiken
    """
    # Wird im nächsten Schritt implementiert
    return "Dashboard - Coming soon!"

@app.route('/api/reload_faces', methods=['POST'])
def reload_faces():
    """
    API: Lädt bekannte Gesichter neu
    """
    load_known_faces()
    return jsonify({'success': True, 'count': len(known_face_names)})

def main():
    """
    Hauptfunktion
    """
    print("=" * 60)
    print("🚀 Pi-Top Face Recognition System")
    print("=" * 60)
    
    # Kamera initialisieren
    if not initialize_camera():
        print("\n⚠️  Server startet ohne Kamera...")
    
    # Bekannte Gesichter laden
    load_known_faces()
    
    # Cleanup alte Detections
    cleanup_old_detections()
    
    # 🚀 Starte AI Worker Thread
    ai_connector = threading.Thread(target=ai_worker_thread, daemon=True)
    ai_connector.start()
    
    print("\n🌐 Server-URLs:")
    print(f"   Lokal:        http://localhost:{SERVER_PORT}")
    print(f"   Netzwerk:     http://0.0.0.0:{SERVER_PORT}")
    print("\n📡 Seiten:")
    print(f"   Live-Stream:  http://localhost:{SERVER_PORT}/")
    print(f"   Enrollment:   http://localhost:{SERVER_PORT}/enroll")
    print(f"   Dashboard:    http://localhost:{SERVER_PORT}/dashboard")
    print("\n⏹️  Drücke Ctrl+C zum Beenden")
    print("=" * 60)
    
    try:
        app.run(
            host='0.0.0.0',
            port=SERVER_PORT,
            debug=False,
            threaded=True,
            use_reloader=False
        )
    except KeyboardInterrupt:
        print("\n\n🛑 Server wird beendet...")
    except Exception as e:
        print(f"\n❌ Fehler: {e}")
        sys.exit(1)
    finally:
        if camera:
            camera.release()
            print("📹 Kamera wurde freigegeben.")
        print("✨ Auf Wiedersehen!")

if __name__ == '__main__':
    main()
