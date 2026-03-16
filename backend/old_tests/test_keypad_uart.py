import serial
import time

def test_keypad():
    print("🚀 UART-Keypad Test gestartet...")
    print("Stelle sicher, dass das Keypad im 'UART' Port steckt!")
    
    try:
        # /dev/serial0 ist der Standard-UART beim Raspberry Pi
        ser = serial.Serial("/dev/serial0", 9600, timeout=1)
        print(f"✅ Port {ser.name} geöffnet. Warte auf Eingabe...")
        
        while True:
            if ser.in_waiting > 0:
                # Rohdaten lesen
                raw_data = ser.read(ser.in_waiting)
                print(f"📥 Empfangen (Roh): {raw_data.hex().upper()}")
                
                # Mapping laut Dokumentation
                mapping = {
                    0xE1: "1", 0xE2: "2", 0xE3: "3",
                    0xE4: "4", 0xE5: "5", 0xE6: "6",
                    0xE7: "7", 0xE8: "8", 0xE9: "9",
                    0xEA: "*", 0xEB: "0", 0xEC: "#"
                }
                
                for byte in raw_data:
                    key = mapping.get(byte)
                    if key:
                        print(f"✨ Taste erkannt: {key}")
            
            time.sleep(0.1)
            
    except Exception as e:
        print(f"❌ Fehler: {e}")
        print("\nTipps:")
        print("1. Ist das Keypad im UART-Port?")
        print("2. Führe 'sudo raspi-config' -> Interface -> Serial -> Console: No, Hardware: Yes aus.")
        print("3. Hast du 'pyserial' installiert? (pip3 install pyserial)")

if __name__ == "__main__":
    test_keypad()
