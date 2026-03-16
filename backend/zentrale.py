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
# Port-Belegung:
#   D0 = Grüner Button Schalter  (input)
#   D1 = Grüner Button LED       (output)
#   D3 = Roter Button Schalter   (input)
#   D2 = Roter Button LED        (output)
has_hw = False
btn_accept = btn_reject = None
led_green_btn = led_red_btn = None
try:
    from pitop.pma import Button, LED
    btn_accept   = Button("D0")
    led_green_btn = LED("D1")
    btn_reject   = Button("D3")
    led_red_btn  = LED("D2")

    # Beim Start beide Button-LEDs kurz aufleuchten lassen (Selbsttest)
    led_green_btn.on(); led_red_btn.on()
    time.sleep(0.5)
    led_green_btn.off(); led_red_btn.off()

    has_hw = True
    print("✅ Hardware initialisiert — D0/D1=Grün, D3/D2=Rot")
except Exception as e:
    print(f"⚠️ Hardware nicht gefunden — Terminal-Simulation aktiv. ({e})")

def set_button_leds(state: str):
    """'an' = beide leuchten, 'gruen' = nur grün, 'rot' = nur rot, 'aus' = beide aus"""
    if not led_green_btn: return
    if state == "an":
        led_green_btn.on();  led_red_btn.on()
    elif state == "gruen":
        led_green_btn.on();  led_red_btn.off()
    elif state == "rot":
        led_green_btn.off(); led_red_btn.on()
    else:
        led_green_btn.off(); led_red_btn.off()

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
        with request_lock:
            if current_request and current_request['status'] == 'pending':
                set_button_leds("an")   # beide Button-LEDs an → Wärter soll reagieren
                if btn_accept.is_pressed:
                    current_request['status'] = 'accepted'
                    print(f"\n✅ Zentrale (D0 Grün): Zugriff ERLAUBT für {current_request['name']}")
                    log_to_db(current_request)
                    set_button_leds("gruen")
                    time.sleep(1)
                    set_button_leds("aus")
                elif btn_reject.is_pressed:
                    current_request['status'] = 'rejected'
                    print(f"\n❌ Zentrale (D3 Rot): Zugriff ABGELEHNT für {current_request['name']}")
                    log_to_db(current_request)
                    set_button_leds("rot")
                    time.sleep(1)
                    set_button_leds("aus")
            else:
                set_button_leds("aus")  # kein Request → LEDs aus
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
