#!/usr/bin/env python3
import time
import sys
from gpiozero import DigitalInputDevice
try:
    import smbus2
except ImportError:
    smbus2 = None

try:
    import serial
except ImportError:
    serial = None

try:
    from pitop import Pitop
    from pitop.pma import FoundationPlate
except ImportError:
    Pitop = None
    FoundationPlate = None

# Mapping der Pi-Top Foundation Plate Ports auf GPIO Pins
PORTS = {
    "D1_P1": 18, "D1_P2": 19,
    "D2_P1": 20, "D2_P2": 21,
    "D3_P1": 22, "D3_P2": 23,
    "D4_P1": 24, "D4_P2": 25,
    "A1": 4, "A2": 5, "A3": 6, "A4": 12,
    "I2C_SDA": 2, "I2C_SCL": 3,
    "UART_TX": 14, "UART_RX": 15
}

def scan_i2c(bus):
    found = []
    if not bus: return found
    for addr in range(0x03, 0x78):
        try:
            bus.write_quick(addr)
            found.append(addr)
        except:
            pass
    return found

def monitor_ports():
    print("\n� SUPER-MONITOR (pi-top Edition)")
    print("========================================")
    
    # pi-top Power-Up
    device = None
    if Pitop:
        try:
            print("🔋 Initialisiere pi-top Hardware...")
            device = Pitop()
            plate = FoundationPlate()
            print(f"✅ Foundation Plate erkannt (Akku: {device.battery.capacity}%)")
        except Exception as e:
            print(f"⚠️ pi-topd Dienst nicht erreichbar oder Plate fehlt: {e}")

    # I2C Initialisierung
    bus = None
    if smbus2:
        try:
            bus = smbus2.SMBus(1)
            print("📡 I2C Bus 1 aktiv.")
        except:
            print("⚠️ I2C Bus 1 konnte nicht geöffnet werden.")

    # UART Initialisierung (für das ATtiny1616 Keypad)
    ser = None
    if serial:
        try:
            ser = serial.Serial("/dev/serial0", 9600, timeout=0.01)
            print("📟 UART Port (/dev/serial0) für Keypad geöffnet.")
        except:
            print("⚠️ UART Port nicht verfügbar.")

    devices = {}
    last_states = {}

    # Digital Pins initialisieren
    for name, pin in PORTS.items():
        try:
            devices[name] = DigitalInputDevice(pin, pull_up=True)
            last_states[name] = devices[name].value
            print(f"✅ Überwache {name} (GPIO {pin})")
        except:
            pass

    print("\n🚀 Monitoring läuft! Warte auf Hardware-Signale...\n")
    
    last_i2c_devices = []

    try:
        while True:
            # 1. Digital Pin Überwachung
            for name, device_pin in devices.items():
                current_val = device_pin.value
                if current_val != last_states[name]:
                    status = "HIGH" if current_val else "LOW"
                    print(f"🔔 [DIGITAL] {name}: {status}")
                    last_states[name] = current_val

            # 2. UART / Keypad Überwachung (ATtiny1616)
            if ser and ser.in_waiting > 0:
                data = ser.read(1)[0]
                # Mapping für das UART Keypad
                mapping = {0xE1:"1", 0xE2:"2", 0xE3:"3", 0xE4:"4", 0xE5:"5", 0xE6:"6", 0xE7:"7", 0xE8:"8", 0xE9:"9", 0xEB:"0", 0xEA:"*", 0xEC:"#"}
                key = mapping.get(data)
                if key:
                    print(f"🎯 [KEYPAD] UART Taste erkannt: {key} (Hex: {hex(data)})")
                else:
                    print(f"📡 [UART] Unbekanntes Byte empfangen: {hex(data)}")

            # 3. I2C Bus Scan (alle 2 Sekunden)
            if int(time.time()) % 2 == 0:
                current_i2c = scan_i2c(bus)
                if current_i2c != last_i2c_devices:
                    new = [hex(a) for a in current_i2c if a not in last_i2c_devices]
                    if new: print(f"✨ [I2C] Neu erkannt: {new}")
                    last_i2c_devices = current_i2c

            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n🛑 Monitor beendet.")
        if ser: ser.close()

if __name__ == "__main__":
    monitor_ports()

if __name__ == "__main__":
    monitor_ports()
