#!/usr/bin/env python3
"""
Pi-Top Kamera-Server mit automatischer Kamera-Erkennung und Head-Tracking
Startet einen Flask-Webserver für Live-Kamera-Streaming mit Gesichtserkennung
"""

from flask import Flask, Response, render_template_string, request, jsonify
import cv2
import threading
import sys
import os

app = Flask(__name__)

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

# Head-Tracking Einstellungen
head_tracking_enabled = True
face_cascade = None
detected_faces_count = 0

def find_camera():
    """
    Sucht automatisch nach verfügbaren Kameras und gibt die erste funktionierende zurück
    """
    print("🔍 Suche nach verfügbaren Kameras...")
    
    # Teste verschiedene Kamera-Indizes (0-5)
    for index in range(6):
        print(f"   Teste Kamera-Index {index}...", end=" ")
        
        # Versuche Kamera zu öffnen
        test_cam = cv2.VideoCapture(index)
        
        if test_cam.isOpened():
            # Teste ob wir tatsächlich ein Frame bekommen
            ret, frame = test_cam.read()
            if ret and frame is not None:
                # Kamera gefunden!
                width = int(test_cam.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(test_cam.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = int(test_cam.get(cv2.CAP_PROP_FPS))
                backend = test_cam.getBackendName()
                
                print(f"✅ Gefunden! ({width}x{height} @ {fps}fps, Backend: {backend})")
                
                # Kamera-Info speichern
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

def load_face_cascade():
    """
    Lädt den Haar Cascade Classifier für Gesichtserkennung
    Sucht an vielen verschiedenen Orten und gibt Debug-Info aus
    """
    global face_cascade
    
    print("\n🎯 Lade Head-Tracking Modell...")
    print(f"   OpenCV Version: {cv2.__version__}")
    
    # Versuche verschiedene Pfade für den Haar Cascade
    cascade_paths = []
    
    # 1. Versuche cv2.data (neuere OpenCV Versionen)
    if hasattr(cv2, 'data'):
        cv2_data_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        cascade_paths.append(cv2_data_path)
        print(f"   📍 cv2.data verfügbar: {cv2_data_path}")
    else:
        print("   ⚠️ cv2.data nicht verfügbar (ältere OpenCV Version)")
    
    # 2. Standard System-Pfade
    cascade_paths.extend([
        '/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
        '/usr/local/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
        '/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml',
        '/usr/local/share/opencv/haarcascades/haarcascade_frontalface_default.xml',
        '/opt/opencv/haarcascades/haarcascade_frontalface_default.xml',
        # Homebrew Pfade (Mac)
        '/opt/homebrew/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
        '/usr/local/Cellar/opencv/*/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
        # Raspberry Pi spezifische Pfade
        '/home/pi/.local/lib/python3.*/site-packages/cv2/data/haarcascade_frontalface_default.xml',
        '/usr/lib/python3/dist-packages/cv2/data/haarcascade_frontalface_default.xml',
    ])
    
    # 3. Versuche im aktuellen Verzeichnis
    local_cascade = os.path.join(os.path.dirname(__file__), 'haarcascade_frontalface_default.xml')
    cascade_paths.append(local_cascade)
    
    print(f"   🔍 Durchsuche {len(cascade_paths)} mögliche Pfade...")
    
    # Versuche jeden Pfad
    for i, path in enumerate(cascade_paths, 1):
        # Expandiere Wildcards in Pfaden
        import glob
        expanded_paths = glob.glob(path) if '*' in path else [path]
        
        for expanded_path in expanded_paths:
            if os.path.exists(expanded_path):
                print(f"   ✓ Pfad {i} existiert: {expanded_path}")
                try:
                    face_cascade = cv2.CascadeClassifier(expanded_path)
                    if not face_cascade.empty():
                        print(f"   ✅ Haar Cascade erfolgreich geladen!")
                        print(f"   📁 Pfad: {expanded_path}")
                        return True
                    else:
                        print(f"   ⚠️ Datei existiert, aber Cascade ist leer")
                except Exception as e:
                    print(f"   ❌ Fehler beim Laden: {e}")
    
    # 4. Letzter Versuch: Suche mit find-Kommando (nur auf Unix-Systemen)
    print("   🔎 Versuche Datei mit System-Suche zu finden...")
    try:
        import subprocess
        result = subprocess.run(
            ['find', '/usr', '-name', 'haarcascade_frontalface_default.xml', '-type', 'f'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.stdout.strip():
            found_path = result.stdout.strip().split('\n')[0]
            print(f"   💡 Datei gefunden: {found_path}")
            face_cascade = cv2.CascadeClassifier(found_path)
            if not face_cascade.empty():
                print(f"   ✅ Haar Cascade erfolgreich geladen!")
                return True
    except Exception as e:
        print(f"   ⚠️ System-Suche fehlgeschlagen: {e}")
    
    # 5. Letzter Versuch: Automatischer Download
    print("   🌐 Versuche Datei automatisch herunterzuladen...")
    download_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'haarcascade_frontalface_default.xml')
    
    try:
        import urllib.request
        url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
        
        print(f"   📥 Lade herunter von: {url}")
        urllib.request.urlretrieve(url, download_path)
        
        if os.path.exists(download_path):
            print(f"   ✅ Download erfolgreich: {download_path}")
            face_cascade = cv2.CascadeClassifier(download_path)
            if not face_cascade.empty():
                print(f"   ✅ Haar Cascade erfolgreich geladen!")
                return True
    except Exception as e:
        print(f"   ❌ Download fehlgeschlagen: {e}")
    
    print("   ❌ Haar Cascade nicht gefunden - Head-Tracking deaktiviert")
    print("   💡 Tipp: Führe aus: ./download_cascade.sh")
    return False


def initialize_camera():
    """
    Initialisiert die Kamera mit optimalen Einstellungen
    """
    global camera
    
    camera = find_camera()
    
    if camera is None:
        print("\n⚠️  WARNUNG: Keine Kamera gefunden!")
        print("   Der Server startet trotzdem, aber es wird kein Video-Stream verfügbar sein.")
        return False
    
    # Optimale Einstellungen setzen
    print("\n⚙️  Konfiguriere Kamera-Einstellungen...")
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_FPS, 30)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduziert Latenz
    
    # Aktualisierte Werte auslesen
    camera_info['width'] = int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))
    camera_info['height'] = int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
    camera_info['fps'] = int(camera.get(cv2.CAP_PROP_FPS))
    
    print(f"   ✅ Auflösung: {camera_info['width']}x{camera_info['height']}")
    print(f"   ✅ FPS: {camera_info['fps']}")
    print(f"   ✅ Backend: {camera_info['backend']}")
    
    return True

def generate_frames():
    """
    Generator-Funktion für Video-Streaming mit Head-Tracking
    """
    global camera, detected_faces_count
    
    if camera is None:
        # Fallback: Zeige Fehlerbild
        yield b'--frame\r\nContent-Type: text/plain\r\n\r\nKeine Kamera verfuegbar\r\n'
        return
    
    while True:
        with camera_lock:
            success, frame = camera.read()
            
            if not success:
                print("⚠️ Fehler beim Lesen des Kamera-Frames")
                break
            
            # Head-Tracking anwenden (wenn aktiviert)
            if head_tracking_enabled and face_cascade is not None:
                # Frame in Graustufen konvertieren für bessere Erkennung
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Gesichter erkennen
                faces = face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,      # Wie stark das Bild bei jeder Skala verkleinert wird
                    minNeighbors=5,       # Wie viele Nachbarn jedes Rechteck haben sollte
                    minSize=(30, 30),     # Minimale Gesichtsgröße
                    flags=cv2.CASCADE_SCALE_IMAGE
                )
                
                detected_faces_count = len(faces)
                
                # Zeichne Boxen um erkannte Gesichter
                for i, (x, y, w, h) in enumerate(faces):
                    # Hauptbox (grün mit Gradient-Effekt)
                    color = (0, 255, 0)  # Grün in BGR
                    thickness = 3
                    
                    # Zeichne Rechteck
                    cv2.rectangle(frame, (x, y), (x+w, y+h), color, thickness)
                    
                    # Zeichne Ecken für modernen Look
                    corner_length = 20
                    corner_thickness = 4
                    
                    # Oben links
                    cv2.line(frame, (x, y), (x + corner_length, y), color, corner_thickness)
                    cv2.line(frame, (x, y), (x, y + corner_length), color, corner_thickness)
                    
                    # Oben rechts
                    cv2.line(frame, (x+w, y), (x+w - corner_length, y), color, corner_thickness)
                    cv2.line(frame, (x+w, y), (x+w, y + corner_length), color, corner_thickness)
                    
                    # Unten links
                    cv2.line(frame, (x, y+h), (x + corner_length, y+h), color, corner_thickness)
                    cv2.line(frame, (x, y+h), (x, y+h - corner_length), color, corner_thickness)
                    
                    # Unten rechts
                    cv2.line(frame, (x+w, y+h), (x+w - corner_length, y+h), color, corner_thickness)
                    cv2.line(frame, (x+w, y+h), (x+w, y+h - corner_length), color, corner_thickness)
                    
                    # Label mit Hintergrund
                    label = f"Kopf #{i+1}"
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.7
                    font_thickness = 2
                    
                    # Textgröße berechnen
                    (text_width, text_height), baseline = cv2.getTextSize(
                        label, font, font_scale, font_thickness
                    )
                    
                    # Hintergrund-Rechteck für Text
                    cv2.rectangle(
                        frame,
                        (x, y - text_height - 10),
                        (x + text_width + 10, y),
                        color,
                        -1  # Gefüllt
                    )
                    
                    # Text zeichnen
                    cv2.putText(
                        frame,
                        label,
                        (x + 5, y - 5),
                        font,
                        font_scale,
                        (0, 0, 0),  # Schwarz
                        font_thickness
                    )
                    
                    # Zentrum des Gesichts markieren
                    center_x = x + w // 2
                    center_y = y + h // 2
                    cv2.circle(frame, (center_x, center_y), 5, (0, 0, 255), -1)  # Roter Punkt
                
                # Info-Text oben links
                info_text = f"Koepfe erkannt: {detected_faces_count}"
                cv2.putText(
                    frame,
                    info_text,
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2
                )
            
            # Frame in JPEG konvertieren (85% Qualität für gute Balance)
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            
            if ret:
                frame_bytes = buffer.tobytes()
                
                # Frame als multipart stream senden
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    """
    Haupt-Seite mit Video-Stream und moderner UI
    """
    html = """
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pi-Top Kamera Stream</title>
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
                backdrop-filter: blur(10px);
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
            
            .status {
                display: inline-block;
                width: 12px;
                height: 12px;
                background: #00ff00;
                border-radius: 50%;
                margin-right: 8px;
                animation: pulse 2s infinite;
                box-shadow: 0 0 10px #00ff00;
            }
            
            @keyframes pulse {
                0%, 100% { 
                    opacity: 1;
                    transform: scale(1);
                }
                50% { 
                    opacity: 0.6;
                    transform: scale(1.1);
                }
            }
            
            .controls {
                margin-top: 20px;
                display: flex;
                gap: 10px;
                justify-content: center;
                flex-wrap: wrap;
            }
            
            button {
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
            }
            
            button:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(0,0,0,0.3);
            }
            
            button:active {
                transform: translateY(0);
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
            
            .footer {
                margin-top: 20px;
                padding: 15px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                color: white;
                text-align: center;
                font-size: 14px;
            }
            
            @media (max-width: 600px) {
                h1 {
                    font-size: 1.8em;
                }
                
                .container {
                    padding: 20px;
                }
                
                button {
                    padding: 10px 20px;
                    font-size: 14px;
                }
            }
        </style>
    </head>
    <body>
        <h1>🎥 Pi-Top Kamera Stream</h1>
        
        <div class="container">
            <div class="video-container">
                <img id="videoStream" src="{{ url_for('video_feed') }}" alt="Kamera Stream">
            </div>
            
            <div class="info">
                <span class="status" id="statusDot"></span>
                <strong id="statusText">Live Stream aktiv</strong>
            </div>
            
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-label">Kamera</div>
                    <div class="stat-value">Index {{ camera_index }}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Auflösung</div>
                    <div class="stat-value">{{ width }}x{{ height }}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">FPS</div>
                    <div class="stat-value">{{ fps }}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Backend</div>
                    <div class="stat-value">{{ backend }}</div>
                </div>
                <div class="stat-item" style="background: linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%);">
                    <div class="stat-label">Head-Tracking</div>
                    <div class="stat-value" id="trackingStatus">{{ 'AN' if tracking_enabled else 'AUS' }}</div>
                </div>
            </div>
            
            <div class="controls">
                <button onclick="location.reload()">🔄 Neu laden</button>
                <button onclick="toggleFullscreen()">⛶ Vollbild</button>
                <button onclick="takeSnapshot()">📸 Snapshot</button>
                <button onclick="toggleTracking()" id="trackingBtn">🎯 Tracking AN/AUS</button>
            </div>
        </div>
        
        <div class="footer">
            ⌨️ Shortcuts: <strong>F</strong> = Vollbild | <strong>S</strong> = Snapshot | <strong>R</strong> = Neu laden | <strong>T</strong> = Tracking
        </div>
        
        <script>
            const videoStream = document.getElementById('videoStream');
            const statusDot = document.getElementById('statusDot');
            const statusText = document.getElementById('statusText');
            
            // Vollbild-Funktion
            function toggleFullscreen() {
                const container = document.querySelector('.video-container');
                if (!document.fullscreenElement) {
                    container.requestFullscreen().catch(err => {
                        alert('Fehler beim Vollbild: ' + err.message);
                    });
                } else {
                    document.exitFullscreen();
                }
            }
            
            // Snapshot-Funktion
            function takeSnapshot() {
                const canvas = document.createElement('canvas');
                canvas.width = videoStream.naturalWidth;
                canvas.height = videoStream.naturalHeight;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(videoStream, 0, 0);
                
                // Download als Bild
                const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
                const link = document.createElement('a');
                link.download = 'pitop_snapshot_' + timestamp + '.jpg';
                link.href = canvas.toDataURL('image/jpeg', 0.95);
                link.click();
            }
            
            // Verbindungsstatus überwachen
            videoStream.onerror = function() {
                statusDot.style.background = '#ff0000';
                statusDot.style.boxShadow = '0 0 10px #ff0000';
                statusText.textContent = 'Verbindung unterbrochen';
            };
            
            videoStream.onload = function() {
                statusDot.style.background = '#00ff00';
                statusDot.style.boxShadow = '0 0 10px #00ff00';
                statusText.textContent = 'Live Stream aktiv';
            };
            
            
            // Head-Tracking umschalten
            function toggleTracking() {
                fetch('/toggle_tracking', {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    const status = data.enabled ? 'AN' : 'AUS';
                    document.getElementById('trackingStatus').textContent = status;
                    alert('Head-Tracking: ' + status);
                })
                .catch(err => {
                    console.error('Fehler beim Umschalten:', err);
                });
            }
            
            // Tastatur-Shortcuts
            document.addEventListener('keydown', function(e) {
                if (e.key === 'f' || e.key === 'F') {
                    e.preventDefault();
                    toggleFullscreen();
                } else if (e.key === 's' || e.key === 'S') {
                    e.preventDefault();
                    takeSnapshot();
                } else if (e.key === 'r' || e.key === 'R') {
                    e.preventDefault();
                    location.reload();
                } else if (e.key === 't' || e.key === 'T') {
                    e.preventDefault();
                    toggleTracking();
                }
            });
        </script>
    </body>
    </html>
    """
    return render_template_string(
        html,
        camera_index=camera_info['index'],
        width=camera_info['width'],
        height=camera_info['height'],
        fps=camera_info['fps'],
        backend=camera_info['backend'],
        tracking_enabled=head_tracking_enabled
    )

@app.route('/video_feed')
def video_feed():
    """
    Video-Stream Route - liefert MJPEG-Stream
    """
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    """
    API-Endpunkt für Kamera-Status
    """
    if camera and camera.isOpened():
        return {
            'status': 'active',
            'camera_index': camera_info['index'],
            'width': camera_info['width'],
            'height': camera_info['height'],
            'fps': camera_info['fps'],
            'backend': camera_info['backend'],
            'head_tracking': {
                'enabled': head_tracking_enabled,
                'faces_detected': detected_faces_count,
                'model_loaded': face_cascade is not None
            }
        }
    else:
        return {
            'status': 'inactive',
            'error': 'Keine Kamera verfügbar'
        }, 503

@app.route('/toggle_tracking', methods=['POST'])
def toggle_tracking():
    """
    API-Endpunkt zum Umschalten des Head-Trackings
    """
    global head_tracking_enabled
    
    head_tracking_enabled = not head_tracking_enabled
    
    return jsonify({
        'enabled': head_tracking_enabled,
        'message': f"Head-Tracking {'aktiviert' if head_tracking_enabled else 'deaktiviert'}"
    })


def main():
    """
    Hauptfunktion - startet den Server
    """
    print("=" * 60)
    print("🚀 Pi-Top Kamera-Server")
    print("=" * 60)
    
    # Kamera initialisieren
    if not initialize_camera():
        print("\n⚠️  Server startet ohne Kamera...")
    
    # Head-Tracking Modell laden
    load_face_cascade()
    
    print("\n🌐 Server-URLs:")
    print("   Lokal:        http://localhost:8080")
    print("   Netzwerk:     http://0.0.0.0:8080")
    print("\n📡 API-Endpunkte:")
    print("   Status:       http://localhost:8080/status")
    print("   Video-Stream: http://localhost:8080/video_feed")
    print("\n⏹️  Drücke Ctrl+C zum Beenden")
    print("=" * 60)
    
    try:
        # Server starten
        app.run(
            host='0.0.0.0',
            port=8080,
            debug=False,
            threaded=True,
            use_reloader=False  # Wichtig: Verhindert doppelte Kamera-Initialisierung
        )
    except KeyboardInterrupt:
        print("\n\n🛑 Server wird beendet...")
    except Exception as e:
        print(f"\n❌ Fehler: {e}")
        sys.exit(1)
    finally:
        # Aufräumen
        if camera:
            camera.release()
            print("📹 Kamera wurde freigegeben.")
        print("✨ Auf Wiedersehen!")

if __name__ == '__main__':
    main()