#!/bin/bash

echo "🔍 DIAGNOSE & FIX NETZWERK/FIREWALL"
echo "======================================"

# 1. Zeige IP Adressen
echo "📡 Meine IP Adressen:"
hostname -I

# 2. Prüfe ob UFW (Firewall) an ist
if command -v ufw > /dev/null; then
    echo "\n🛡️ UFW Status:"
    sudo ufw status verbose
    
    echo "\n🔓 Erlaube Ports 8000, 5000, 22..."
    sudo ufw allow 22/tcp
    sudo ufw allow 8000/tcp
    sudo ufw allow 5000/tcp
    sudo ufw allow 8080/tcp
    # Optional: Firewall testweise deaktivieren
    # sudo ufw disable
else
    echo "\nℹ️ UFW ist nicht installiert."
fi

# 3. Prüfe IPTABLES (die 'echte' Firewall)
echo "\n🧱 IPTables Regeln (Chain INPUT):"
sudo iptables -L INPUT -n --line-numbers | head -n 20

# 4. Flush IPTables (VORSICHT: Kann Docker Regeln löschen falls vorhanden)
# Wir flushen nicht hart, aber wir fügen eine Regel hinzu, die Port 8000 sicher erlaubt.
echo "\n✅ Erzwinge Port 8000 ACCEPT in iptables..."
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 5000 -j ACCEPT

# 5. Prüfe Listening Ports
echo "\n👂 Da lauscht aktuell jemand:"
sudo lsof -i -P -n | grep LISTEN

echo "\n✨ FERTIG. Versuch den Zugriff jetzt nochmal."
