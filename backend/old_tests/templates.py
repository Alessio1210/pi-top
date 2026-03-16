"""
HTML Templates für Face Recognition System
"""

ENROLLMENT_PAGE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Person Registrieren - Pi-Top</title>
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
            padding: 20px;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        
        h1 {
            color: #333;
            margin-bottom: 30px;
            text-align: center;
        }
        
        .video-preview {
            width: 100%;
            max-width: 640px;
            margin: 0 auto 30px;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            background: #000;
        }
        
        .video-preview img {
            width: 100%;
            display: block;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
        }
        
        input[type="text"],
        textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        input[type="text"]:focus,
        textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        
        textarea {
            resize: vertical;
            min-height: 80px;
        }
        
        .button-group {
            display: flex;
            gap: 10px;
            margin-top: 30px;
        }
        
        button, .btn {
            flex: 1;
            padding: 15px 30px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
            text-align: center;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }
        
        .btn-secondary {
            background: #f0f0f0;
            color: #333;
        }
        
        .btn-secondary:hover {
            background: #e0e0e0;
        }
        
        .btn-capture {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            margin-bottom: 20px;
        }
        
        .alert {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-weight: 500;
        }
        
        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .alert-error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .alert-info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }
        
        .hidden {
            display: none;
        }
        
        .loading {
            text-align: center;
            padding: 20px;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .face-detected {
            background: #d4edda;
            color: #155724;
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            margin-bottom: 20px;
            font-weight: 600;
        }
        
        .no-face {
            background: #fff3cd;
            color: #856404;
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            margin-bottom: 20px;
            font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>➕ Neue Person registrieren</h1>
        
        <div id="alertContainer"></div>
        
        <div class="video-preview">
            <img id="videoStream" src="{{ url_for('video_feed') }}" alt="Kamera Stream">
        </div>
        
        <div id="faceStatus" class="hidden"></div>
        
        <button class="btn btn-capture" onclick="capturePhoto()">📸 Foto aufnehmen</button>
        
        <form id="enrollForm" onsubmit="submitEnrollment(event)">
            <div class="form-group">
                <label for="personName">Name *</label>
                <input type="text" id="personName" name="name" required 
                       placeholder="z.B. Max Mustermann">
            </div>
            
            <div class="form-group">
                <label for="notes">Notizen (optional)</label>
                <textarea id="notes" name="notes" 
                          placeholder="z.B. Klasse 10A, Schüler"></textarea>
            </div>
            
            <input type="hidden" id="faceData" name="face_data">
            
            <div class="button-group">
                <a href="/" class="btn btn-secondary">❌ Abbrechen</a>
                <button type="submit" class="btn btn-primary">✅ Person registrieren</button>
            </div>
        </form>
    </div>
    
    <script>
        let capturedFaceData = null;
        
        function showAlert(message, type = 'info') {
            const container = document.getElementById('alertContainer');
            const alert = document.createElement('div');
            alert.className = `alert alert-${type}`;
            alert.textContent = message;
            container.innerHTML = '';
            container.appendChild(alert);
            
            // Auto-remove after 5 seconds
            setTimeout(() => {
                alert.remove();
            }, 5000);
        }
        
        async function capturePhoto() {
            try {
                showAlert('📸 Nehme Foto auf...', 'info');
                
                const response = await fetch('/api/capture_face', {
                    method: 'POST'
                });
                
                const data = await response.json();
                
                if (data.success) {
                    capturedFaceData = data.face_encoding;
                    document.getElementById('faceData').value = JSON.stringify(data.face_encoding);
                    
                    showAlert('✅ Gesicht erfolgreich erfasst!', 'success');
                    document.getElementById('faceStatus').className = 'face-detected';
                    document.getElementById('faceStatus').textContent = '✅ Gesicht erfasst - Bereit zur Registrierung';
                } else {
                    showAlert('❌ ' + data.error, 'error');
                    document.getElementById('faceStatus').className = 'no-face';
                    document.getElementById('faceStatus').textContent = '⚠️ Kein Gesicht erkannt - Bitte erneut versuchen';
                }
            } catch (error) {
                showAlert('❌ Fehler beim Aufnehmen: ' + error.message, 'error');
            }
        }
        
        async function submitEnrollment(event) {
            event.preventDefault();
            
            if (!capturedFaceData) {
                showAlert('❌ Bitte erst ein Foto aufnehmen!', 'error');
                return;
            }
            
            const formData = {
                name: document.getElementById('personName').value,
                notes: document.getElementById('notes').value,
                face_encoding: capturedFaceData
            };
            
            try {
                showAlert('💾 Speichere Person...', 'info');
                
                const response = await fetch('/api/enroll_person', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formData)
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showAlert('✅ Person erfolgreich registriert!', 'success');
                    
                    // Reload faces
                    await fetch('/api/reload_faces', { method: 'POST' });
                    
                    // Redirect nach 2 Sekunden
                    setTimeout(() => {
                        window.location.href = '/dashboard';
                    }, 2000);
                } else {
                    showAlert('❌ ' + data.error, 'error');
                }
            } catch (error) {
                showAlert('❌ Fehler beim Speichern: ' + error.message, 'error');
            }
        }
    </script>
</body>
</html>
"""

DASHBOARD_PAGE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Pi-Top Face Recognition</title>
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
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            text-align: center;
        }
        
        .stat-value {
            font-size: 48px;
            font-weight: bold;
            color: #667eea;
            margin: 10px 0;
        }
        
        .stat-label {
            font-size: 14px;
            color: #666;
            text-transform: uppercase;
            font-weight: 600;
        }
        
        .section {
            background: white;
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .section h2 {
            margin-bottom: 20px;
            color: #333;
        }
        
        .person-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 20px;
        }
        
        .person-card {
            background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            transition: transform 0.3s;
        }
        
        .person-card:hover {
            transform: translateY(-5px);
        }
        
        .person-name {
            font-size: 18px;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
        }
        
        .person-stats {
            font-size: 14px;
            color: #666;
        }
        
        .detection-list {
            max-height: 400px;
            overflow-y: auto;
        }
        
        .detection-item {
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 5px;
        }
        
        .detection-name {
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
        }
        
        .detection-time {
            font-size: 12px;
            color: #666;
        }
        
        .detection-confidence {
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            margin-left: 10px;
        }
        
        .controls {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }
        
        .btn-secondary {
            background: white;
            color: #333;
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #999;
        }
        
        .empty-state-icon {
            font-size: 64px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Dashboard - Face Recognition System</h1>
        
        <div class="controls">
            <a href="/" class="btn btn-secondary">🏠 Zurück zum Stream</a>
            <a href="/enroll" class="btn btn-primary">➕ Person registrieren</a>
            <button onclick="refreshData()" class="btn btn-secondary">🔄 Aktualisieren</button>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Registrierte Personen</div>
                <div class="stat-value" id="totalPersons">{{ total_persons }}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Erkennungen Heute</div>
                <div class="stat-value" id="detectionsToday">{{ detections_today }}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Verschiedene Personen Heute</div>
                <div class="stat-value" id="uniqueToday">{{ unique_today }}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Gesamt Erkennungen (30 Tage)</div>
                <div class="stat-value" id="totalDetections">{{ total_detections }}</div>
            </div>
        </div>
        
        <div class="section">
            <h2>👥 Registrierte Personen</h2>
            <div class="person-grid" id="personGrid">
                {% if persons %}
                    {% for person in persons %}
                    <div class="person-card">
                        <div class="person-name">{{ person.name }}</div>
                        <div class="person-stats">
                            {{ person.total_detections or 0 }} Erkennungen<br>
                            {% if person.last_seen %}
                            Zuletzt: {{ person.last_seen_formatted }}
                            {% else %}
                            Noch nie gesehen
                            {% endif %}
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="empty-state">
                        <div class="empty-state-icon">👤</div>
                        <p>Noch keine Personen registriert</p>
                    </div>
                {% endif %}
            </div>
        </div>
        
        <div class="section">
            <h2>🕐 Letzte Erkennungen</h2>
            <div class="detection-list" id="detectionList">
                {% if recent_detections %}
                    {% for detection in recent_detections %}
                    <div class="detection-item">
                        <div class="detection-name">
                            {{ detection.person_name }}
                            <span class="detection-confidence">{{ (detection.confidence * 100)|int }}%</span>
                        </div>
                        <div class="detection-time">{{ detection.detected_at_formatted }}</div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="empty-state">
                        <div class="empty-state-icon">🔍</div>
                        <p>Noch keine Erkennungen</p>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
    
    <script>
        async function refreshData() {
            location.reload();
        }
        
        // Auto-refresh alle 30 Sekunden
        setInterval(refreshData, 30000);
    </script>
</body>
</html>
"""
