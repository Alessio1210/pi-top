from pitop import Pitop
import time

try:
    print("Versuche pi-top Foundation Plate zu initialisieren...")
    p = Pitop()
    # Das bloße Erstellen des Objekts schaltet oft die Stromzufuhr frei
    time.sleep(1)
    print("Batterie-Stand:", p.battery.capacity, "%")
    print("Falls das hier ohne Fehler durchläuft, ist die Verbindung da!")
except Exception as e:
    print(f"❌ Fehler bei der pi-top Verbindung: {e}")