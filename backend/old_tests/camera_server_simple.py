from flask import Flask, Response, render_template_string
import cv2
import threading

app = Flask(__name__)

# USB-Kamera initialisieren (Index 0 ist normalerweise die erste USB-Kamera)
camera = cv2.VideoCapture(0)

# Kamera-Einstellungen optimieren
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
camera.set(cv2.CAP_PROP_FPS, 30)

# Lock für Thread-Sicherheit
camera_lock = threading.Lock()

def generate_frames():
    """Generator-Funktion für Video-Streaming"""
    while True:
        with camera_lock:
            success, frame = camera.read()
            
            if not success:
                print("⚠️ Fehler beim Lesen des Kamera-Frames")
                break
            else:
                # Frame in JPEG konvertieren
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    frame_bytes = buffer.tobytes()
                    
                    # Frame als multipart stream senden
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    """Haupt-Seite mit Video-Stream"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Pi-Top Kamera Stream</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
        <h1>🎥 Pi-Top USB Kamera</h1>
        
        <div class="container">
            <div class="video-container">
                <img id="videoStream" src="{{ url_for('video_feed') }}" alt="Kamera Stream">
            </div>
            
            <div class="info">
                <span class="status" id="statusDot"></span>
                <strong id="statusText">Live Stream aktiv</strong> - USB Kamera verbunden
            </div>
            
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-label">Auflösung</div>
                    <div class="stat-value">640x480</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">FPS</div>
                    <div class="stat-value">30</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Format</div>
                    <div class="stat-value">MJPEG</div>
                </div>
            </div>
            
            <div class="controls">
                <button onclick="location.reload()">🔄 Neu laden</button>
                <button onclick="toggleFullscreen()">⛶ Vollbild</button>
                <button onclick="takeSnapshot()">📸 Snapshot</button>
            </div>
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
                const link = document.createElement('a');
                link.download = 'snapshot_' + new Date().getTime() + '.jpg';
                link.href = canvas.toDataURL('image/jpeg');
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
            
            // Tastatur-Shortcuts
            document.addEventListener('keydown', function(e) {
                if (e.key === 'f' || e.key === 'F') {
                    toggleFullscreen();
                } else if (e.key === 's' || e.key === 'S') {
                    takeSnapshot();
                } else if (e.key === 'r' || e.key === 'R') {
                    location.reload();
                }
            });
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/video_feed')
def video_feed():
    """Video-Stream Route"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    """Status-Endpunkt für API-Abfragen"""
    is_opened = camera.isOpened()
    return {
        'camera': 'USB',
        'status': 'active' if is_opened else 'inactive',
        'width': int(camera.get(cv2.CAP_PROP_FRAME_WIDTH)),
        'height': int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        'fps': int(camera.get(cv2.CAP_PROP_FPS))
    }

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Pi-Top Kamera-Server startet...")
    print("=" * 50)
    
    # Kamera-Status prüfen
    if camera.isOpened():
        print("✅ USB-Kamera erfolgreich verbunden!")
        print(f"📐 Auflösung: {int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
        print(f"🎬 FPS: {int(camera.get(cv2.CAP_PROP_FPS))}")
    else:
        print("❌ FEHLER: Kamera konnte nicht geöffnet werden!")
        print("   Überprüfe, ob die USB-Kamera angeschlossen ist.")
    
    print("\n🌐 Server-URLs:")
    print("   Lokal:    http://localhost:8080")
    print("   Netzwerk: http://0.0.0.0:8080")
    print("\n⌨️  Tastatur-Shortcuts im Browser:")
    print("   F = Vollbild")
    print("   S = Snapshot")
    print("   R = Neu laden")
    print("\n⏹️  Drücke Ctrl+C zum Beenden")
    print("=" * 50)
    
    try:
        app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n🛑 Server wird beendet...")
    finally:
        # Kamera freigeben
        if camera:
            camera.release()
            print("📹 Kamera wurde geschlossen.")
        print("✨ Auf Wiedersehen!")
