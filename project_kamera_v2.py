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
import json
import base64
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image
import uuid

# Supabase
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Supabase Client
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Globale Variablen
camera = None
camera_lock = threading.Lock()
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

# Detection Settings
DETECTION_CONFIDENCE_THRESHOLD = float(os.getenv('DETECTION_CONFIDENCE_THRESHOLD', 0.6))
DETECTION_COOLDOWN_SECONDS = 5  # Nur alle 5 Sekunden in DB speichern

# Statistiken
stats = {
    'total_detections_today': 0,
    'unique_persons_today': set(),
    'last_cleanup': datetime.now()
}

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
        
    except Exception as e:
        print(f"   ❌ Fehler beim Laden: {e}")

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
        
        supabase.table('detections').insert(detection_data).execute()
        
        # Update cooldown
        last_detection_time[person_id] = now
        
        # Update Stats
        stats['total_detections_today'] += 1
        stats['unique_persons_today'].add(person_name)
        
        print(f"   💾 Erkennung gespeichert: {person_name} ({confidence:.2%})")
        
    except Exception as e:
        print(f"   ❌ Fehler beim Speichern: {e}")

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
    camera.set(cv2.CAP_PROP_FPS, 30)
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
    global camera
    
    if camera is None:
        yield b'--frame\r\nContent-Type: text/plain\r\n\r\nKeine Kamera verfuegbar\r\n'
        return
    
    # Process every Nth frame for face recognition (performance)
    process_this_frame = 0
    
    while True:
        with camera_lock:
            success, frame = camera.read()
            
            if not success:
                print("⚠️ Fehler beim Lesen des Kamera-Frames")
                break
            
            # Face Recognition (nur jeden 3. Frame)
            if face_recognition_enabled and process_this_frame % 3 == 0:
                # Resize für schnellere Verarbeitung
                small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                
                # Finde Gesichter
                face_locations = face_recognition.face_locations(rgb_small_frame)
                face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
                
                for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                    # Skaliere zurück
                    top *= 4
                    right *= 4
                    bottom *= 4
                    left *= 4
                    
                    # Vergleiche mit bekannten Gesichtern
                    name = "Unbekannt"
                    confidence = 0.0
                    person_id = None
                    
                    if len(known_face_encodings) > 0:
                        # Berechne Distanzen
                        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                        best_match_index = np.argmin(face_distances)
                        
                        # Confidence = 1 - distance
                        confidence = 1 - face_distances[best_match_index]
                        
                        if confidence > DETECTION_CONFIDENCE_THRESHOLD:
                            name = known_face_names[best_match_index]
                            person_id = known_face_ids[best_match_index]
                            
                            # Speichere Detection in DB
                            save_detection(person_id, name, confidence)
                    
                    # Zeichne Box
                    color = (0, 255, 0) if name != "Unbekannt" else (0, 0, 255)
                    thickness = 3
                    
                    # Rechteck
                    cv2.rectangle(frame, (left, top), (right, bottom), color, thickness)
                    
                    # Ecken für modernen Look
                    corner_length = 20
                    corner_thickness = 4
                    
                    # Oben links
                    cv2.line(frame, (left, top), (left + corner_length, top), color, corner_thickness)
                    cv2.line(frame, (left, top), (left, top + corner_length), color, corner_thickness)
                    
                    # Oben rechts
                    cv2.line(frame, (right, top), (right - corner_length, top), color, corner_thickness)
                    cv2.line(frame, (right, top), (right, top + corner_length), color, corner_thickness)
                    
                    # Unten links
                    cv2.line(frame, (left, bottom), (left + corner_length, bottom), color, corner_thickness)
                    cv2.line(frame, (left, bottom), (left, bottom - corner_length), color, corner_thickness)
                    
                    # Unten rechts
                    cv2.line(frame, (right, bottom), (right - corner_length, bottom), color, corner_thickness)
                    cv2.line(frame, (right, bottom), (right, bottom - corner_length), color, corner_thickness)
                    
                    # Label mit Name und Confidence
                    if name != "Unbekannt":
                        label = f"{name} ({confidence:.0%})"
                    else:
                        label = "Unbekannt"
                    
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.7
                    font_thickness = 2
                    
                    # Textgröße
                    (text_width, text_height), baseline = cv2.getTextSize(
                        label, font, font_scale, font_thickness
                    )
                    
                    # Hintergrund für Text
                    cv2.rectangle(
                        frame,
                        (left, top - text_height - 10),
                        (left + text_width + 10, top),
                        color,
                        -1
                    )
                    
                    # Text
                    cv2.putText(
                        frame,
                        label,
                        (left + 5, top - 5),
                        font,
                        font_scale,
                        (255, 255, 255),  # Weiß
                        font_thickness
                    )
            
            process_this_frame += 1
            
            # Frame in JPEG konvertieren
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

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
    
    return render_template_string(
        html,
        total_persons=persons_count,
        detections_today=detections_today,
        confidence_threshold=DETECTION_CONFIDENCE_THRESHOLD
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
    # Wird im nächsten Schritt implementiert
    return "Enrollment-Seite - Coming soon!"

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
    
    print("\n🌐 Server-URLs:")
    print("   Lokal:        http://localhost:8080")
    print("   Netzwerk:     http://0.0.0.0:8080")
    print("\n📡 Seiten:")
    print("   Live-Stream:  http://localhost:8080/")
    print("   Enrollment:   http://localhost:8080/enroll")
    print("   Dashboard:    http://localhost:8080/dashboard")
    print("\n⏹️  Drücke Ctrl+C zum Beenden")
    print("=" * 60)
    
    try:
        app.run(
            host='0.0.0.0',
            port=8080,
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
