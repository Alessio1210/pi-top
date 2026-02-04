#!/usr/bin/env python3
import time
import sys
from gpiozero import Button, DigitalInputDevice

# Mapping der Pi-Top Foundation Plate Ports auf GPIO Pins
# Digital Ports (D1-D4)
# Port D1: GPIO 18, 19
# Port D2: GPIO 20, 21
# Port D3: GPIO 22, 23
# Port D4: GPIO 24, 25
# Analog Ports (A1-A4) - Digital genutzt (nur Pin 1)
# Port A1: GPIO 4
# Port A2: GPIO 5
# Port A3: GPIO 6
# Port A4: GPIO 12

PORTS = {
    "D1_P1": 18, "D1_P2": 19,
    "D2_P1": 20, "D2_P2": 21,
    "D3_P1": 22, "D3_P2": 23,
    "D4_P1": 24, "D4_P2": 25,
    "A1": 4,
    "A2": 5,
    "A3": 6,
    "A4": 12,
}

def monitor_ports():
    print("🔍 STARTE HARDWARE-MONITOR (ALLE PORTS)")
    print("========================================")
    print("Dieses Skript zeigt an, wenn sich an IRGENDEINEM Port ein Signal ändert.")
    print("Drücke Tasten am Keypad oder berühre Sensoren...")
    print("Beenden mit Strg+C\n")

    devices = {}
    last_states = {}

    # Initialisiere alle Pins als digitale Eingänge
    for name, pin in PORTS.items():
        try:
            # Wir nutzen DigitalInputDevice für Rohdaten
            devices[name] = DigitalInputDevice(pin, pull_up=True)
            last_states[name] = devices[name].value
            print(f"✅ Überwache {name} (GPIO {pin})")
        except Exception as e:
            print(f"❌ Konnte {name} (GPIO {pin}) nicht öffnen: {e}")

    print("\n🚀 Monitoring aktiv! Warte auf Signale...\n")

    try:
        while True:
            for name, device in devices.items():
                current_val = device.value
                if current_val != last_states[name]:
                    status = "HIGH (1)" if current_val else "LOW (0)"
                    timestamp = time.strftime("%H:%M:%S")
                    print(f"🔔 [{timestamp}] Port {name}: ÄNDERUNG -> {status}")
                    last_states[name] = current_val
            time.sleep(0.01) # 100Hz Abtastung
    except KeyboardInterrupt:
        print("\n\n🛑 Monitor beendet.")

if __name__ == "__main__":
    monitor_ports()
