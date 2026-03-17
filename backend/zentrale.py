import os
import time
import threading
from flask import Flask, request, jsonify
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from flask_cors import CORS

# Load environment variables — search from project root (one level up from backend/)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

app = Flask(__name__)
CORS(app)

# Supabase Client
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"⚠️ Supabase Init Fehler: {e}")
    supabase = None

# State for current request
current_request = None
request_lock = threading.Lock()

# Hardware Setup für Zentrale
#   D0 = Grüner Button (Annehmen)
#   D3 = Roter Button  (Ablehnen)
has_hw = False
btn_accept = btn_reject = None
try:
    from pitop.pma import Button
    btn_accept = Button("D0")
    btn_reject = Button("D3")
    has_hw = True
    print("✅ Buttons initialisiert (D0=Annehmen, D3=Ablehnen)")
except Exception as e:
    print(f"⚠️ Hardware nicht gefunden — Terminal-Simulation aktiv. ({e})")

def log_to_db(req_data):
    """Loggt den Zugriff in die Datenbank"""
    if not supabase: return
    try:
        supabase.table('access_logs').insert({
            'person_id': req_data['person_id'],
            'person_name': req_data['name'],
            'status': req_data['status']
        }).execute()
        print("💾 Log in Supabase gespeichert.")
    except Exception as e:
        print(f"⚠️ Fehler beim Speichern in DB: {e}")

def console_input_loop():
    """Terminal-Eingabe für Simulation (wenn keine physikalischen Tasten da sind)"""
    global current_request
    print("\n⌨️  Zentrale läuft... Drücke 'y' um Zugriff zu GEWÄHREN, 'n' um ABZULEHNEN.")
    import sys, tty, termios
    fd = sys.stdin.fileno()
    
    while True:
        try:
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            
            with request_lock:
                if current_request and current_request['status'] == 'pending':
                    if ch.lower() == 'y':
                        current_request['status'] = 'accepted'
                        print(f"\n✅ Zentrale: Zugriff ERLAUBT für {current_request['name']}")
                        log_to_db(current_request)
                    elif ch.lower() == 'n':
                        current_request['status'] = 'rejected'
                        print(f"\n❌ Zentrale: Zugriff ABGELEHNT für {current_request['name']}")
                        log_to_db(current_request)
        except Exception:
            time.sleep(0.1)

def hardware_button_loop():
    """Überwacht die verbundenen Tasten an Pi 2"""
    global current_request
    while True:
        decision = None
        with request_lock:
            if current_request and current_request['status'] == 'pending':
                if btn_accept.is_pressed:
                    current_request['status'] = 'accepted'
                    decision = current_request.copy()
                elif btn_reject.is_pressed:
                    current_request['status'] = 'rejected'
                    decision = current_request.copy()

        if decision:
            if decision['status'] == 'accepted':
                print(f"\n✅ Zentrale (D0 Grün): Zugriff ERLAUBT für {decision['name']}")
            else:
                print(f"\n❌ Zentrale (D3 Rot): Zugriff ABGELEHNT für {decision['name']}")
            log_to_db(decision)
            time.sleep(1)  # Debounce außerhalb des Locks

        time.sleep(0.1)

@app.route('/api/request_access', methods=['POST'])
def handle_access_request():
    """Wird von Pi 1 aufgerufen, um eine Zugriffsanfrage zu stellen"""
    global current_request
    data = request.json
    
    with request_lock:
        current_request = {
            "req_id": str(time.time()),
            "person_id": data.get("person_id"),
            "name": data.get("name"),
            "status": "pending",
            "timestamp": time.time()
        }
    
    print(f"\n🔔 NEUE ZUGRIFFSANFRAGE: {data.get('name')} (ID: {data.get('person_id')})")
    print("   -> Warte auf Bestätigung (D0=Annehmen, D3=Ablehnen, 10s Timeout)")

    log_to_db(current_request)
    return jsonify({"success": True, "req_id": current_request["req_id"]})

@app.route('/api/access_status', methods=['GET'])
def get_access_status():
    """Wird von Pi 1 wiederholt aufgerufen, um die Entscheidung abzufragen"""
    with request_lock:
        if current_request:
            req_id = current_request["req_id"]
            status = current_request["status"]
            
            # Check Timeout (10 Sekunden)
            if status == 'pending' and (time.time() - current_request['timestamp']) > 10:
                current_request['status'] = 'timeout'
                status = 'timeout'
                print(f"\n⏰ Zentrale Timeout: Keine Entscheidung für {current_request['name']} getroffen.")
                log_to_db(current_request)
                
            return jsonify({
                "req_id": req_id,
                "status": status
            })
            
    return jsonify({"req_id": None, "status": "idle"})

if __name__ == '__main__':
    print("=" * 60)
    print("🏢 PI-TOP ZENTRALE (SERVER) - PORT 5001")
    print("=" * 60)
    
    if not has_hw:
        threading.Thread(target=console_input_loop, daemon=True).start()
    else:
        threading.Thread(target=hardware_button_loop, daemon=True).start()
        
    app.run(host='0.0.0.0', port=5001, debug=False)
