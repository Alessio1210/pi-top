from pitop import LED, Button, Buzzer
from time import sleep
import random

print("🎄 Jingle Bells startet! 🔔")

led_rot = LED("D5")        
led_gelb = LED("D6")
led_gruen = LED("D7")
button = Button("D0")
buzzer = Buzzer("D1")

# Noten-Frequenzen (in Hz) - Mittlere Oktave
NOTE_E = 330   # E4
NOTE_F = 349   # F4
NOTE_G = 392   # G4
NOTE_A = 440   # A4
NOTE_B = 494   # B4
NOTE_C = 523   # C5
NOTE_D = 587   # D5
NOTE_E_HIGH = 659  # E5

# Notenlängen (in Sekunden)
QUARTER = 0.3   # Viertelnote
HALF = 0.6      # Halbe Note
EIGHTH = 0.15   # Achtelnote

# Jingle Bells Melodie: (Frequenz, Dauer)
jingle_bells = [
    # "Jin-gle bells, jin-gle bells, jin-gle all the way"
    (NOTE_E, QUARTER), (NOTE_E, QUARTER), (NOTE_E, HALF),
    (NOTE_E, QUARTER), (NOTE_E, QUARTER), (NOTE_E, HALF),
    (NOTE_E, QUARTER), (NOTE_G, QUARTER), (NOTE_C, QUARTER), (NOTE_D, QUARTER),
    (NOTE_E, HALF + QUARTER), (0, QUARTER),  # Pause
    
    # "Oh what fun it is to ride in a one-horse o-pen sleigh"
    (NOTE_F, QUARTER), (NOTE_F, QUARTER), (NOTE_F, QUARTER), (NOTE_F, QUARTER),
    (NOTE_F, QUARTER), (NOTE_E, QUARTER), (NOTE_E, QUARTER), (NOTE_E, EIGHTH), (NOTE_E, EIGHTH),
    (NOTE_E, QUARTER), (NOTE_D, QUARTER), (NOTE_D, QUARTER), (NOTE_E, QUARTER),
    (NOTE_D, HALF), (NOTE_G, HALF),
]

def led_blink_random():
    """Lässt eine zufällige LED aufleuchten"""
    # Alle aus
    led_rot.off()
    led_gelb.off()
    led_gruen.off()
    
    # Zufällige LED auswählen
    choice = random.randint(0, 3)
    if choice == 0:
        led_rot.on()
    elif choice == 1:
        led_gelb.on()
    elif choice == 2:
        led_gruen.on()
    # choice == 3: alle bleiben aus

def play_note(frequency, duration):
    """Spielt eine Note und lässt LEDs blinken"""
    if frequency > 0:
        buzzer.on()
        led_blink_random()
        sleep(duration * 0.9)  # 90% der Zeit klingt die Note
        buzzer.off()
        sleep(duration * 0.1)  # 10% Pause zwischen Noten
    else:
        # Pause
        led_rot.off()
        led_gelb.off()
        led_gruen.off()
        sleep(duration)

def play_jingle_bells():
    """Spielt die komplette Jingle Bells Melodie"""
    print("🎵 Spiele Jingle Bells...")
    for note, duration in jingle_bells:
        play_note(note, duration)
    
    # Finale: Alle LEDs blinken
    for _ in range(3):
        led_rot.on()
        led_gelb.on()
        led_gruen.on()
        sleep(0.2)
        led_rot.off()
        led_gelb.off()
        led_gruen.off()
        sleep(0.2)
    
    print("✨ Fertig!")

# Button-Druck startet die Melodie
button.when_pressed = play_jingle_bells

print("Drücke den Button, um Jingle Bells zu spielen! 🎅")
print("Drücke Ctrl+C zum Beenden.")

# Skript am Leben halten
try:
    while True:
        sleep(0.1)
except KeyboardInterrupt:
    led_rot.off()
    led_gelb.off()
    led_gruen.off()
    buzzer.off()
    print("\n🎄 Frohe Weihnachten! Programm beendet.")
