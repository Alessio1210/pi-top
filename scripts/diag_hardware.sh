#!/bin/bash

echo "🛠️ PI-TOP HARDWARE DIAGNOSE"
echo "=============================="

# 1. Kernel Module Check
echo -n "1. Prüfe I2C Kernel Module... "
if lsmod | grep -q "i2c_dev"; then
    echo "✅ OK"
else
    echo "❌ FEHLT! (sudo modprobe i2c-dev)"
    sudo modprobe i2c-dev
fi

# 2. Device Tree Check
echo -n "2. Prüfe /boot/config.txt... "
if grep -q "dtparam=i2c_arm=on" /boot/config.txt; then
    echo "✅ OK"
else
    echo "❌ DEAKTIVIERT! (Füge dtparam=i2c_arm=on hinzu)"
fi

# 3. Pi-Top Hub Check
echo -n "3. Prüfe Pi-Top Hub Kommunikation... "
if pt-device -i &> /dev/null; then
    echo "✅ OK ($(pt-device -i))"
else
    echo "⚠️ pi-topd Dienst reagiert nicht. Ist die Platte richtig dran?"
fi

# 4. I2C Bus Check
echo "4. Vorhandene I2C Busse:"
ls -l /dev/i2c*

echo -e "\n💡 TIPPS:"
echo "1. Steck das LCD und Keypad aus und wieder ein."
echo "2. Stelle sicher, dass sie in Ports stecken, die mit 'I2C' beschriftet sind."
echo "3. Führe 'sudo raspi-config' -> Interface -> I2C -> Yes aus."
echo "4. Starte den Pi neu: 'sudo reboot'"
