import smbus2
import time

def scan_i2c():
    bus = smbus2.SMBus(1)
    print("🔍 Scanne I2C Bus nach Geräten...")
    found = 0
    for address in range(0x03, 0x78):
        try:
            bus.write_quick(address)
            print(f"✅ Gerät gefunden auf Adresse: 0x{address:02x}")
            found += 1
        except OSError:
            pass
    if found == 0:
        print("❌ Keine Geräte gefunden. Prüfe Kabel und I2C Aktivierung!")
    bus.close()

if __name__ == "__main__":
    scan_i2c()
