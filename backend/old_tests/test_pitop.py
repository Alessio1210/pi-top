from pitop import Pitop
from pitop.pma import LED # Nur zum Testen der Ports
import time

try:
    device = Pitop()
    print(f"✅ pi-top Gerät erkannt: {device.miniscreen.display_device}")
    print("🔋 Akku-Stand:", device.battery.capacity, "%")
    
    # Die pi-top Bibliothek kümmert sich intern um die Stromversorgung der Ports.
    # Wir scannen jetzt nochmal den I2C Bus, während das Pitop-Objekt aktiv ist.
    import smbus2
    bus = smbus2.SMBus(1)
    print("\n🔍 Scanne I2C-Bus 1 erneut...")
    for address in range(0x03, 0x78):
        try:
            bus.write_quick(address)
            print(f"🌟 Gerät gefunden auf: 0x{address:02x}")
        except:
            pass
except Exception as e:
    print(f"❌ Fehler: {e}")
