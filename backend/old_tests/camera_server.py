from flask import Flask, Response, render_template_string
from pitop import Camera
import cv2
import threading

app = Flask(__name__)

# USB-Kamera initialisieren
camera = Camera("USB")

# Lock für Thread-Sicherheit
camera_lock = threading.Lock()

def generate_frames():
    """Generator-Funktion für Video-Streaming"""
    while True:
        with camera_lock:
            # Frame von der Kamera holen
            frame = camera.get_frame()
            
            if frame is not None:
                # Frame in JPEG konvertieren
                ret, buffer = cv2.imencode('.jpg', frame)
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
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                margin: 0;
                padding: 20px;
                display: flex;
                flex-direction: column;
                align-items: center;
                min-height: 100vh;
            }
            
            h1 {
                color: white;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
                margin-bottom: 30px;
                font-size: 2.5em;
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
            }
            
            img {
                width: 100%;
                height: auto;
                display: block;
            }
            
            .info {
                margin-top: 20px;
                padding: 15px;
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                border-radius: 10px;
                color: white;
                text-align: center;
            }
            
            .status {
                display: inline-block;
                width: 12px;
                height: 12px;
                background: #00ff00;
                border-radius: 50%;
                margin-right: 8px;
                animation: pulse 2s infinite;
            }
            
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            
            .controls {
                margin-top: 20px;
                display: flex;
                gap: 10px;
                justify-content: center;
            }
            
            button {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 16px;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            }
            
            button:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(0,0,0,0.3);
            }
            
            button:active {
                transform: translateY(0);
            }
        </style>
    </head>
    <body>
        <h1>🎥 Pi-Top USB Kamera</h1>
        
        <div class="container">
            <div class="video-container">
                <img src="{{ url_for('video_feed') }}" alt="Kamera Stream">
            </div>
            
            <div class="info">
                <span class="status"></span>
                <strong>Live Stream aktiv</strong> - USB Kamera verbunden
            </div>
            
            <div class="controls">
                <button onclick="location.reload()">🔄 Neu laden</button>
                <button onclick="toggleFullscreen()">⛶ Vollbild</button>
            </div>
        </div>
        
        <script>
            function toggleFullscreen() {
                const img = document.querySelector('.video-container img');
                if (!document.fullscreenElement) {
                    img.requestFullscreen().catch(err => {
                        alert('Fehler beim Vollbild: ' + err.message);
                    });
                } else {
                    document.exitFullscreen();
                }
            }
            
            // Zeige Verbindungsstatus
            const img = document.querySelector('.video-container img');
            img.onerror = function() {
                document.querySelector('.status').style.background = '#ff0000';
                document.querySelector('.info strong').textContent = 'Verbindung unterbrochen';
            };
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
    return {
        'camera': 'USB',
        'status': 'active',
        'resolution': camera.resolution if hasattr(camera, 'resolution') else 'unknown'
    }

if __name__ == '__main__':
    print("🚀 Starte Flask-Server...")
    print("📹 Kamera wird initialisiert...")
    print("🌐 Server läuft auf: http://localhost:5000")
    print("⏹️  Drücke Ctrl+C zum Beenden")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n🛑 Server wird beendet...")
    finally:
        # Kamera aufräumen
        if camera:
            print("📹 Kamera wird geschlossen...")
