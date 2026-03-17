#!/usr/bin/env python3
"""
Pi-Top Face Recognition System mit Supabase
Schulprojekt: 30-Tage Speicherung mit Timestamps
"""

from flask import Flask, Response, request, jsonify, send_from_directory
from flask_cors import CORS
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
import serial
import subprocess
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables — relativ zur Datei, egal von wo gestartet
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
# Flask-Logging deaktivieren (gegen das Chaos im Terminal)
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

SERVER_PORT = 8000

# Supabase Client
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase verbunden")
except Exception as e:
    print(f"⚠️ Supabase Init Fehler: {e} — läuft ohne Datenbank")
    supabase = None

# Telegram & Discord Konfiguration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

telegram_alert_cooldown = datetime.min
unknown_face_counter = 0
UNKNOWN_THRESHOLD = 15  # Ca. 2-3 Sekunden durchgehend unbekannt vor Alarm

ZENTRALE_URL = os.getenv('ZENTRALE_URL', 'http://localhost:5001')
access_state = "IDLE"
access_cooldown = 0
door_status = "closed"   # closed | checking | open | denied
lcd_locked = False        # True während access_flow → AI-Thread schreibt nicht drüber
_last_lcd  = ("", "")    # Cache: nur schreiben wenn Inhalt sich ändert

# ── I2C Keypad (PCF8574, 0x20) ─────────────────────────────────────────────
KEYPAD_ADDR = 0x20
KEYPAD_KEYS = [
    ['1','2','3','A'],
    ['4','5','6','B'],
    ['7','8','9','C'],
    ['*','0','#','D'],
]
keypad_bus = None
try:
    import smbus2 as _smbus2
    keypad_bus = _smbus2.SMBus(1)
    keypad_bus.read_byte(KEYPAD_ADDR)
    print("⌨️  Keypad initialisiert (I2C 0x20)")
except Exception as _e:
    keypad_bus = None
    print(f"⚠️ Keypad nicht gefunden: {_e}")

def _scan_keypad_once():
    """Gibt gedrückte Taste zurück oder None. PCF8574: lower nibble=Reihen, upper=Spalten."""
    if keypad_bus is None:
        return None
    try:
        for row in range(4):
            out = 0xF0 | (0x0F ^ (1 << row))
            keypad_bus.write_byte(KEYPAD_ADDR, out)
            time.sleep(0.002)
            val = keypad_bus.read_byte(KEYPAD_ADDR)
            cols = (val >> 4) & 0x0F
            if cols != 0x0F:
                for col in range(4):
                    if not (cols >> col) & 1:
                        return KEYPAD_KEYS[row][col]
    except Exception:
        pass
    return None

def read_pin_input(prompt="PIN eingeben", length=4, timeout=20):
    """Liest PIN vom Keypad. Zeigt * auf LCD. # = Bestätigen, * = Löschen.
    Gibt eingegebenen PIN-String zurück, oder '' bei Timeout."""
    pin = ""
    lcd(prompt, "_" * length, force=True)
    last_key = None
    deadline = time.time() + timeout
    while time.time() < deadline:
        key = _scan_keypad_once()
        if key != last_key:
            if key is not None:
                if key == '*':
                    pin = pin[:-1]
                    lcd(prompt, "*" * len(pin) + "_" * (length - len(pin)), force=True)
                elif key == '#':
                    break
                elif key.isdigit() and len(pin) < length:
                    pin += key
                    display = "*" * len(pin) + "_" * (length - len(pin))
                    lcd(prompt, display, force=True)
                    if len(pin) == length:
                        time.sleep(0.3)
                        break
            last_key = key
        elif key is None:
            last_key = None
        time.sleep(0.05)
    return pin

# Hardware Konfiguration
BUZZER_PIN = 6  # A2 auf Foundation Plate ist GPIO 6
# Wir nutzen gpiozero für einfache Ansteuerung
try:
    from pitop import Pitop
    from pitop.pma import Buzzer as PitopBuzzer
    from pitop.pma import LED as PitopLED
    from pitop.pma import FoundationPlate
    buzzer = PitopBuzzer(BUZZER_PIN)
    led_green = PitopLED("D2")
    led_red = PitopLED("D3")
    print("🔊 Buzzer initialisiert auf GPIO 6 (A2)")
    print("💡 LEDs initialisiert (Grün: D2, Rot: D3)")
except ImportError:
    Pitop = None
    FoundationPlate = None
    buzzer = None
    led_green = None
    led_red = None
    print(f"⚠️ Buzzer/LED Fehler: gpiozero oder pitop nicht gefunden.")
except Exception as e:
    buzzer = None
    led_green = None
    led_red = None
    print(f"⚠️ Hardware Fehler: {e}")

# Ampel — direkt an GPIO via RPi.GPIO (BCM: 26=Rot, 19=Gelb, 13=Grün)
AMPEL_ROT   = 26
AMPEL_GELB  = 19
AMPEL_GRUEN = 13
ampel_ok = False
try:
    import RPi.GPIO as GPIO
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(AMPEL_ROT,   GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(AMPEL_GELB,  GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(AMPEL_GRUEN, GPIO.OUT, initial=GPIO.LOW)
    ampel_ok = True
    print(f"🚦 Ampel initialisiert (BCM Rot:{AMPEL_ROT}, Gelb:{AMPEL_GELB}, Grün:{AMPEL_GRUEN})")
except Exception as e:
    print(f"⚠️ Ampel nicht verfügbar: {e}")

def set_ampel(color):
    """Setzt die Ampelfarbe: 'rot', 'gelb', 'gruen' oder 'aus'"""
    if not ampel_ok: return
    GPIO.output(AMPEL_ROT,   GPIO.LOW)
    GPIO.output(AMPEL_GELB,  GPIO.LOW)
    GPIO.output(AMPEL_GRUEN, GPIO.LOW)
    if   color == "rot":   GPIO.output(AMPEL_ROT,   GPIO.HIGH)
    elif color == "gelb":  GPIO.output(AMPEL_GELB,  GPIO.HIGH)
    elif color == "gruen": GPIO.output(AMPEL_GRUEN, GPIO.HIGH)


# Hilfsfunktion für saubere Terminal-Ausgabe
def cprint(msg):
    print(f"\r{msg}", flush=True)

def lcd(line1, line2="", force=False):
    """Schreibt aufs LCD — nur wenn Inhalt sich geändert hat (Cache).
    Respektiert lcd_locked: AI-Thread darf nicht überschreiben während access_flow läuft.
    force=True ignoriert den Lock (für access_flow selbst)."""
    global _last_lcd
    if lcd_locked and not force:
        return
    if (line1, line2) == _last_lcd:
        return
    _last_lcd = (line1, line2)
    hw.write_lcd(line1, line2)


def set_led_color(color):
    if color == "green":
        if led_green: led_green.on()
        if led_red: led_red.off()
    elif color == "red":
        if led_green: led_green.off()
        if led_red: led_red.on()
    else:
        if led_green: led_green.off()
        if led_red: led_red.off()

def handle_access_flow(person_id, name):
    global access_state, access_cooldown, door_status, lcd_locked

    print(f"\n📡 Sende Zugriffsanfrage fuer {name} an die Zentrale...")
    lcd("Bitte warten", "Zentrale prueft", force=True)
    set_ampel("gelb")
    door_status = "checking"

    try:
        res = requests.post(f"{ZENTRALE_URL}/api/request_access", json={"person_id": person_id, "name": name}, timeout=3)
        if res.status_code == 200:
            for _ in range(12):
                time.sleep(1)
                status_res = requests.get(f"{ZENTRALE_URL}/api/access_status", timeout=2)
                if status_res.status_code == 200:
                    status = status_res.json().get("status")
                    if status == "accepted":
                        print(f"✅ Zentrale hat Zugriff GEWAEHRT fuer {name}")
                        lcd("ANGENOMMEN", name[:16], force=True)
                        time.sleep(1)

                        # ── PIN-Abfrage ──────────────────────────────
                        pin_ok = True
                        if keypad_bus is not None:
                            # PIN aus Supabase laden
                            db_pin = None
                            if supabase:
                                try:
                                    r = supabase.table('persons').select('pin').eq('id', person_id).execute()
                                    if r.data:
                                        db_pin = r.data[0].get('pin')
                                except Exception:
                                    pass

                            if db_pin:
                                lcd("Bitte PIN", "eingeben:", force=True)
                                entered = read_pin_input("PIN eingeben:", length=4)
                                if entered == str(db_pin):
                                    print(f"🔑 PIN korrekt für {name}")
                                    lcd("PIN korrekt", "Willkommen!", force=True)
                                else:
                                    print(f"❌ Falscher PIN für {name}")
                                    lcd("Falscher PIN", "Zugang verweigert", force=True)
                                    set_led_color("red")
                                    set_ampel("rot")
                                    door_status = "denied"
                                    if buzzer:
                                        buzzer.on(); time.sleep(0.6); buzzer.off()
                                    time.sleep(3)
                                    pin_ok = False

                        if pin_ok:
                            set_led_color("green")
                            set_ampel("gruen")
                            door_status = "open"
                            if buzzer:
                                buzzer.on(); time.sleep(0.2); buzzer.off()
                            time.sleep(10)
                        break
                    elif status == "rejected":
                        print(f"❌ Zentrale hat Zugriff ABGELEHNT fuer {name}")
                        lcd("ABGELEHNT", name[:16], force=True)
                        set_led_color("red")
                        set_ampel("rot")
                        door_status = "denied"
                        if buzzer:
                            buzzer.on(); time.sleep(0.6); buzzer.off()
                        time.sleep(3)
                        break
                    elif status == "timeout":
                        print("⏰ Timeout bei der Zentrale.")
                        lcd("ABGELEHNT", "Timeout", force=True)
                        set_led_color("red")
                        set_ampel("rot")
                        door_status = "denied"
                        time.sleep(3)
                        break

            # Zurücksetzen
            set_led_color("off")
            set_ampel("aus")
            door_status = "closed"
            lcd("Bereit", "Warte auf Gesicht", force=True)
    except Exception as e:
        print(f"⚠️ Fehler bei Verbindung zur Zentrale: {e}")
        lcd("NETZWERKFEHLER", "Zentrale offline", force=True)
        set_led_color("red")
        set_ampel("rot")
        door_status = "denied"
        time.sleep(2)
        set_led_color("off")
        set_ampel("aus")
        door_status = "closed"
    finally:
        access_cooldown = time.time() + 5
        access_state = "IDLE"
        lcd_locked = False

# hardware_pin_buffer etc.
# I2C Treiber für Hardware-Komponenten (LCD, Keypad, Fingerprint)
class HardwareManager:
    def __init__(self):
        self.cpp_process = None
        self.last_line1 = ""
        self.last_line2 = ""
        
        # 1. C++ Core-Engine starten (übernimmt Hardware-Scanning)
        self.init_cpp_engine()
        
        # 2. pi-top Power-Status (optional)
        if Pitop:
            try:
                self.pt_device = Pitop()
                cprint(f"🔋 System-Akku: {self.pt_device.battery.capacity}%")
            except: pass

    def init_cpp_engine(self):
        """Kompiliert und startet die C++ Core-Engine"""
        cpp_source = "core_engine.cpp"
        cpp_binary = "./core_engine"
        
        try:
            # Automatisches Kompilieren falls Source-Datei vorhanden
            if os.path.exists(cpp_source):
                cprint("🛠 Kompiliere Hochleistungs-Core (C++)...")
                subprocess.run(["clang++", "-O3", cpp_source, "-o", cpp_binary], check=True)
            
            if os.path.exists(cpp_binary):
                cprint("🚀 Starte C++ Core Engine...")
                self.cpp_process = subprocess.Popen(
                    [cpp_binary], 
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
                threading.Thread(target=self._monitor_cpp_engine, daemon=True).start()
        except Exception as e:
            cprint(f"⚠️ Core Engine Fehler: {e}")

    def _monitor_cpp_engine(self):
        """Hört auf Nachrichten von der C++ Engine"""
        if not self.cpp_process: return
        for line in self.cpp_process.stdout:
            line = line.strip()
            if line.startswith("KEY:"):
                key = line.split(":")[1]
                process_key_input(key)
            elif line.startswith("FOUND:"):
                cprint(f"✨ Hardware erkannt: {line.split(':')[1]}")
            elif line == "READY":
                cprint("✅ HOCHLEISTUNGS-CORE IST BEREIT")
                self.write_lcd("Hallo!", "Bereit...")

    def write_lcd(self, line1, line2=""):
        """Schickt Text-Befehle an die C++ Engine"""
        if self.cpp_process:
            try:
                msg = f"LCD:{line1}|{line2}\n"
                self.cpp_process.stdin.write(msg)
                self.cpp_process.stdin.flush()
            except: pass
        
        # Lokale State-Kontrolle für Console
        if line1 != self.last_line1 or line2 != self.last_line2:
            self.last_line1, self.last_line2 = line1, line2
            print(f"\r📟 [LCD] {line1:10} | {line2:10}", flush=True)

    def set_lcd_color(self, r, g, b):
        """Schickt Farbbefehle an die C++ Engine"""
        if self.cpp_process:
            try:
                msg = f"RGB:{r},{g},{b}\n"
                self.cpp_process.stdin.write(msg)
                self.cpp_process.stdin.flush()
            except: pass

    def read_fingerprint(self):
        # Fingerprint bleibt vorerst deaktiviert, bis er in C++ ist
        return None

hw = HardwareManager()
hardware_pin_buffer = ""
last_key_state = 0

def physical_hardware_loop():
    """
    Thread der Fingerprint und sonstige I2C Sensoren überwacht
    (Keypad wird jetzt über die C++ Engine in HardwareManager gesteuert)
    """
    while is_running:
        # 1. Fingerprint Abfrage via I2C
        finger_id = hw.read_fingerprint()
        if finger_id is not None:
            verify_fingerprint_id(finger_id)

        time.sleep(0.1)

def console_keypad_simulation():
    """
    Erlaubt es, das Keypad über das Terminal am Mac zu simulieren.
    """
    cprint("⌨️  SIMULATION AKTIV: 0-9, Enter, C (q zum Beenden)")
    import sys, tty, termios
    fd = sys.stdin.fileno()
    
    while is_running:
        try:
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            
            if ch in "0123456789":
                process_key_input(ch)
            elif ch in "\r\n": 
                process_key_input("#")
            elif ch in "*Cc\x7f": 
                process_key_input("*")
            elif ch in "fF":
                cprint("☝️ [SIM] Simuliere Fingerprint Scan...")
                verify_fingerprint_id(1)
            elif ch in "qQ":
                break
        except:
            time.sleep(0.5)

def process_key_input(key):
    """
    Zentrale Logik für Keypad-Eingaben
    """
    global hardware_pin_buffer
    
    if key == "#": # ENTER
        if hardware_pin_buffer:
            if last_detected_person["id"]:
                verify_physical_pin(last_detected_person["id"], hardware_pin_buffer)
            else:
                hw.write_lcd("Kein Gesicht", "erkannt!")
                time.sleep(2)
                hw.write_lcd("Bereit", "PIN/Finger:")
            hardware_pin_buffer = ""
            
    elif key == "*": # CLEAR
        hardware_pin_buffer = ""
        hw.write_lcd("Geloescht", "")
        time.sleep(1)
        hw.write_lcd("Bereit", "PIN/Finger:")
        
    else: # NUMMER
        if len(hardware_pin_buffer) < 4:
            hardware_pin_buffer += key
        
        # Zeige maskierte PIN am LCD
        masked_pin = "*" * len(hardware_pin_buffer)
        hw.write_lcd("PIN Eingabe:", f"{masked_pin} (ID:{key})")

def verify_fingerprint_id(finger_id):
    """
    Sucht die Person zum Fingerprint in der Datenbank und loggt sie ein.
    """
    try:
        # Hier müsste eine Spalte 'fingerprint_id' in der DB existieren
        response = supabase.table('persons').select('name, employee_number').eq('fingerprint_id', finger_id).execute()
        
        if response.data:
            user = response.data[0]
            print(f"✅ Fingerprint Match: {user['name']}")
            hw.set_lcd_color(0, 255, 0) # Grün
            hw.write_lcd("FINGER OK", user['name'])
            if buzzer: buzzer.beep(0.2, 0, 1)
            # Speichere Detection
            save_detection(user.get('id'), user['name'], 1.0)
        else:
            print(f"❌ Fingerprint ID {finger_id} unbekannt")
            hw.set_lcd_color(255, 165, 0) # Orange
            hw.write_lcd("FINGER UNBEKANNT", f"ID: {finger_id}")
            if buzzer: buzzer.beep(0.4, 0, 1)
        
        time.sleep(3)
        hw.set_lcd_color(255, 255, 255)
        hw.write_lcd("Bereit", "PIN oder Finger")
    except Exception as e:
        print(f"⚠️ Fingerprint Fehler: {e}")
        hw.write_lcd("FEHLER", "DB Check failed")


def verify_physical_pin(person_id, pin):
    """
    Hilfsfunktion für das physikalische Keypad (nutzt API Logik)
    """
    try:
        print(f"⏳ [DB] Prüfe PIN {pin} für Person {person_id}...", flush=True)
        response = supabase.table('persons').select('pin, name, employee_number').eq('id', person_id).execute()
        
        if not response.data: 
            print("❌ Person nicht in DB gefunden")
            return
        
        user = response.data[0]
        db_pin = str(user.get('pin'))
        
        if db_pin == pin:
            print(f"✅ PIN KORREKT für {user['name']}", flush=True)
            hw.write_lcd("Hallo!", user['name'])
            if buzzer: buzzer.beep(0.2, 0, 1)
        else:
            print(f"❌ PIN FALSCH (Eingabe: {pin}, Soll: {db_pin})", flush=True)
            hw.write_lcd("FEHLER", "Falscher PIN")
            if buzzer: buzzer.beep(0.6, 0, 1)
            send_discord_alert(f"⚠️ **Keypad FEHLER**: Falscher PIN für {user['name']}")
            
        time.sleep(2)
        hw.write_lcd("Hallo!", "Bereit...")
    except Exception as e:
        print(f"⚠️ API Fehler: {e}", flush=True)



# Globale Variablen
# Globale Variablen
camera = None
camera_lock = threading.Lock()
current_frame = None
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

# Status Tracking für UI
last_detected_person = {
    "id": None,
    "name": None,
    "timestamp": 0
}


# Statistiken
stats = {
    'total_detections_today': 0,
    'unique_persons_today': set(),
    'last_cleanup': datetime.now()
}

# Globale Variable für aktuellen Frame (für Snapshots)
current_frame = None

# Stabilitätspuffer — verhindert Flackern zwischen Name und "Unbekannt"
STABLE_DURATION = 4.0   # Sekunden, wie lange ein erkanntes Gesicht "eingefroren" bleibt
stable_face = {"name": None, "id": None, "expires_at": 0.0}

# Temporärer Speicher für Enrollment
enrollment_cache = {}

def load_known_faces():
    """
    Lädt alle bekannten Gesichter aus Supabase
    """
    global known_face_encodings, known_face_names, known_face_ids

    if not supabase:
        print("⚠️ Supabase nicht verfügbar — keine Gesichter geladen")
        return

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

    if not supabase:
        return

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

    if not supabase:
        return

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

def send_discord_alert(message, image_bytes=None):
    """
    Sendet eine Nachricht an Discord via Webhook
    """
    if not DISCORD_WEBHOOK_URL:
        return
        
    try:
        data = {
            "content": message,
            "username": "Pi-Top Security"
        }
        
        files = {}
        if image_bytes:
            files = {
                "file": ("alert.jpg", image_bytes)
            }
            
        requests.post(DISCORD_WEBHOOK_URL, data=data, files=files, timeout=5)
        print("   ✅ Discord Alert gesendet")
    except Exception as e:
        print(f"   ❌ Discord Fehler: {e}")

def trigger_alert(frame):
    """
    Startet den Alarm-Prozess (Telegram + Discord)
    """
    global telegram_alert_cooldown
    
    # Cooldown Check
    if datetime.now() < telegram_alert_cooldown:
        return

    # Bild konvertieren
    ret, buffer = cv2.imencode('.jpg', frame)
    if ret:
        print("\n🚨 UNBEKANNTE PERSON - Sende Alarm...")
        telegram_alert_cooldown = datetime.now() + timedelta(seconds=60)
        
        img_bytes = buffer.tobytes()
        
        # Telegram Thread
        t1 = threading.Thread(target=send_telegram_alert_thread, args=(img_bytes,))
        t1.start()
        
        # Discord Thread
        t2 = threading.Thread(target=send_discord_alert, args=("🚨 **ALARM**: Unbekannte Person erkannt!", img_bytes))
        t2.start()
        
        # Hardware Feedback
        if buzzer:
            # Alarm Sound (3x kurz)
            threading.Thread(target=lambda: [buzzer.beep(on_time=0.1, off_time=0.1, n=3)], daemon=True).start()


def ai_worker_thread():
    """
    Hintergrund-Thread für Face Recognition
    """
    global ai_frame_buffer, ai_results, unknown_face_counter, access_state, access_cooldown, lcd_locked
    
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
                        
                        print(f"🎯 [AI] Gesicht erkannt: {name} ({confidence:.0%})", flush=True)
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
            
            # Stabilitätspuffer befüllen
            now_t = time.time()
            for (loc, info) in new_results:
                if info[0] != "Unbekannt":
                    stable_face["name"] = info[0]
                    stable_face["id"]   = known_face_ids[known_face_names.index(info[0])]
                    stable_face["expires_at"] = now_t + STABLE_DURATION
                    break

            # Falls kein Gesicht im Frame aber Puffer noch aktiv → letzten Namen einfrieren
            if not any(n != "Unbekannt" for n in current_face_names_for_alert):
                if now_t < stable_face["expires_at"] and stable_face["name"]:
                    # Ergebnis aus Puffer wiederherstellen — Position aus letztem echten Frame
                    current_face_names_for_alert = [stable_face["name"]]

            # Ergebnisse update
            with ai_results_lock:
                ai_results = new_results

                if current_face_names_for_alert:
                    for (loc, info) in new_results:
                        if info[0] != "Unbekannt":
                            last_detected_person["id"] = known_face_ids[known_face_names.index(info[0])]
                            last_detected_person["name"] = info[0]
                            last_detected_person["timestamp"] = time.time()
                            break
                    # Puffer als Fallback für last_detected_person
                    if not last_detected_person["name"] and stable_face["name"] and now_t < stable_face["expires_at"]:
                        last_detected_person["name"] = stable_face["name"]
                        last_detected_person["id"]   = stable_face["id"]

            # === Alarm Logik & LCD Update ===
            has_known   = any(n != "Unbekannt" for n in current_face_names_for_alert)
            has_unknown = any(n == "Unbekannt" for n in current_face_names_for_alert) and not has_known
            
            if has_known:
                unknown_face_counter = 0
                known_names = [n for n in current_face_names_for_alert if n != "Unbekannt"]
                if known_names:
                    name = known_names[0]
                    if access_state == "IDLE" and time.time() > access_cooldown:
                        access_state = "REQUESTING"
                        lcd_locked = True   # Sofort sperren bevor Thread startet
                        set_ampel("gelb")
                        try:
                            idx = known_face_names.index(name)
                            person_id = known_face_ids[idx]
                        except:
                            person_id = 0
                        threading.Thread(target=handle_access_flow, args=(person_id, name), daemon=True).start()
                    elif access_state == "IDLE":
                        lcd("Hallo!", name)
            elif has_unknown:
                unknown_face_counter += 1
                lcd("Unbekannt", "Wer bist du?")
                if access_state == "IDLE":
                    set_ampel("gelb")
                if unknown_face_counter >= UNKNOWN_THRESHOLD:
                    trigger_alert(frame_to_process)
                    unknown_face_counter = 0
            else:
                # Kein Gesicht → Ampel aus, Bereit
                if access_state == "IDLE":
                    set_ampel("aus")
                if unknown_face_counter > 0:
                    unknown_face_counter -= 1
                if unknown_face_counter == 0:
                    lcd("Hallo!", "Bereit...")

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
    camera.set(cv2.CAP_PROP_FPS, 30) # Zurück auf 30 FPS für Stabilität
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
    
    fail_count = 0
    
    while True:
        with camera_lock:
            success, frame = camera.read()
            
            if not success:
                fail_count += 1
                if fail_count > 10:
                    print("⚠️ Fehler beim Lesen des Kamera-Frames (Gibt auf nach 10 Versuchen)")
                    break
                # Kurze Pause und Retry
                time.sleep(0.1)
                continue
            
            fail_count = 0 # Reset bei Erfolg
            
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
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# ============================================================
# FLASK ROUTES
# ============================================================

@app.route('/')
def index():
    return jsonify({"status": "Pi-Top Face Recognition API is running (CORS enabled)"})

@app.route('/api/events')
def sse_events():
    def generate():
        while is_running:
            try:
                # Polling for changes
                now = time.time()
                detected = False
                name = None
                p_id = None
                
                # Check if someone was recently detected (within 2 seconds)
                if now - last_detected_person.get("timestamp", 0) <= 2:
                    detected = True
                    name = last_detected_person.get("name")
                    p_id = last_detected_person.get("id")
                    
                data = {
                    "event": "status",
                    "detected": detected,
                    "name": name,
                    "id": p_id,
                    "total_persons": len(known_face_names),
                    "detections_today": stats.get('total_detections_today', 0),
                    "door_status": door_status
                }
                yield f"data: {json.dumps(data)}\n\n"
            except Exception as e:
                pass
            time.sleep(1)
            
    return Response(generate(), mimetype='text/event-stream')

@app.route('/video_feed')
def video_feed():
    """
    Video-Stream Route
    """
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/capture_face')
def capture_face_api():
    """Nimmt aktuellen Frame, erkennt Gesicht, gibt Crop-Foto + Encoding zurück."""
    with ai_frame_lock:
        frame = ai_frame_buffer.copy() if ai_frame_buffer is not None else None
    if frame is None:
        return jsonify({'success': False, 'error': 'Kein Kamerabild verfügbar'})
    try:
        small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        locs  = face_recognition.face_locations(rgb)
        if not locs:
            return jsonify({'success': False, 'error': 'Kein Gesicht im Bild erkannt'})
        encs = face_recognition.face_encodings(rgb, locs)
        top, right, bottom, left = [v * 2 for v in locs[0]]
        h, w = frame.shape[:2]
        pad = 30
        crop = frame[max(0,top-pad):min(h,bottom+pad), max(0,left-pad):min(w,right+pad)]
        _, buf = cv2.imencode('.jpg', crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
        photo_b64 = base64.b64encode(buf.tobytes()).decode()
        return jsonify({
            'success': True,
            'photo': f'data:image/jpeg;base64,{photo_b64}',
            'encoding': encs[0].tolist()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/enroll', methods=['POST'])
def enroll_api():
    """Speichert neue Person mit Gesicht in Supabase, lädt known_faces neu."""
    if not supabase:
        return jsonify({'success': False, 'error': 'Supabase nicht verbunden'})
    data      = request.json or {}
    first     = data.get('first_name', '').strip()
    last      = data.get('last_name', '').strip()
    dept      = data.get('department', '').strip()
    pin       = data.get('pin', '') or None
    encoding  = data.get('encoding', [])
    photo_b64 = data.get('photo', '')
    name = f"{first} {last}".strip()
    if not name or not encoding:
        return jsonify({'success': False, 'error': 'Name und Gesicht erforderlich'})
    try:
        photo_url = None
        if photo_b64:
            raw      = base64.b64decode(photo_b64.split(',')[-1])
            filename = f"{uuid.uuid4()}.jpg"
            supabase.storage.from_('person-photos').upload(filename, raw, {'content-type': 'image/jpeg'})
            photo_url = supabase.storage.from_('person-photos').get_public_url(filename)

        row = {'name': name, 'face_encoding': encoding, 'photo_url': photo_url, 'pin': pin}
        if dept:
            row['department'] = dept
        result = supabase.table('persons').insert(row).execute()
        new_id = result.data[0]['id']
        load_known_faces()
        print(f"✅ Neuer Benutzer enrollt: {name} (ID {new_id})")
        return jsonify({'success': True, 'id': new_id, 'name': name})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/enroll_unknown', methods=['POST'])
def enroll_unknown():
    """Zentrale triggert Enrollment für letzte unbekannte Person.
    Sendet Name an Zentrale /api/enroll_user → Zentrale fragt PIN ab."""
    data = request.json or {}
    name = data.get('name') or last_detected_person.get('name', 'Unbekannt')
    try:
        res = requests.post(f"{ZENTRALE_URL}/api/enroll_user", json={"name": name}, timeout=3)
        return jsonify({"success": res.status_code == 200, "name": name})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/current_status')
def current_status_api():
    """
    Gibt den aktuell erkannten User zurück (für das PIN Pad am Mac)
    """
    now = time.time()
    # Wenn die Erkennung älter als 2 Sekunden ist, gilt sie als "weg"
    if now - last_detected_person["timestamp"] > 2:
        return jsonify({'detected': False})
        
    return jsonify({
        'detected': True,
        'id': last_detected_person["id"],
        'name': last_detected_person["name"]
    })


@app.route('/api/verify_pin', methods=['POST'])
def verify_pin_api():
    """
    Überprüft den eingegebenen PIN für eine Person
    """
    data = request.json
    person_id = data.get('person_id')
    pin_input = str(data.get('pin'))
    
    if not person_id or not pin_input:
        return jsonify({'success': False, 'error': 'Fehlende Daten'})
        
    try:
        # Hole richtigen PIN aus DB
        response = supabase.table('persons').select('pin, name, employee_number').eq('id', person_id).execute()
        
        if not response.data:
            return jsonify({'success': False, 'error': 'Person nicht gefunden'})
            
        user = response.data[0]
        correct_pin = str(user.get('pin'))
        username = user.get('name')
        emp_num = user.get('employee_number', '---')
        
        if correct_pin == pin_input:
            # ✅ Richtig
            print(f"✅ PIN korrekt für {username}")
            
            # Hardware Feedback: Success (Kurzer Piep)
            if buzzer:
                threading.Thread(target=lambda: [buzzer.on(), time.sleep(0.2), buzzer.off()], daemon=True).start()
                
            # LCD Update
            if lcd_display:
                lcd_display.write_message(f"Hallo {username}", f"ID: {emp_num}")
            
            return jsonify({'success': True, 'name': username})
        else:
            # ❌ Falsch
            print(f"❌ PIN falsch für {username}")
            
            # LCD Update Error
            if lcd_display:
                lcd_display.write_message("FEHLER", "Falscher PIN")
            
            # Hardware Feedback: Error (Langer tiefer Piep oder mehrmals)

            if buzzer:
                threading.Thread(target=lambda: [buzzer.on(), time.sleep(0.6), buzzer.off()], daemon=True).start()
            
            # Discord Alert bei falschem PIN
            failed_msg = f"⚠️ **Fehlgeschlagener Login**: Falscher PIN eingegeben für **{username}**!"
            threading.Thread(target=send_discord_alert, args=(failed_msg,)).start()
            
            return jsonify({'success': False, 'error': 'Falscher PIN'})
            
    except Exception as e:
        print(f"❌ Fehler bei PIN Check: {e}")
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
    pin = data.get('pin', '0000') # Default PIN
    
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
            'notes': notes,
            'pin': str(pin)
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
    return jsonify({"error": "moved to frontend"}), 301

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
    
    # 🚀 Starte Hardware & Simulations Threads
    hw_thread = threading.Thread(target=physical_hardware_loop, daemon=True)
    hw_thread.start()

    # PIN-Simulation deaktiviert (blockiert Terminal via tty.setraw)
    # sim_thread = threading.Thread(target=console_keypad_simulation, daemon=True)
    # sim_thread.start()
    
    print("\r\n🌐 Server-URLs:")
    print(f"\r   Lokal:        http://localhost:{SERVER_PORT}")
    print(f"\r   Netzwerk:     http://0.0.0.0:{SERVER_PORT}")
    print("\r\n📡 Seiten:")
    print(f"\r   Live-Stream:  http://localhost:{SERVER_PORT}/")
    print(f"\r   Enrollment:   http://localhost:{SERVER_PORT}/enroll")
    print(f"\r   Dashboard:    http://localhost:{SERVER_PORT}/dashboard")
    print("\r\n⏹️  Drücke Ctrl+C zum Beenden")
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
