#!/bin/bash
# Script d'installation automatique POCSAG Monitor Pro

set -e  # Arrêt sur erreur

echo "🚀 Installation POCSAG Monitor Pro"

# Vérification des privilèges root
if [[ $EUID -ne 0 ]]; then
   echo "❌ Ce script doit être exécuté en root (sudo)" 
   exit 1
fi

echo "📦 Installation des dépendances système..."
apt update
apt install -y rtl-sdr multimon-ng python3 python3-pip nginx git

echo "🐍 Installation des dépendances Python..."
pip3 install requests

echo "📁 Création des répertoires..."
mkdir -p /opt/pocsag/src
mkdir -p /var/www/html
mkdir -p /etc/nginx/sites-available

echo "📋 Copie des fichiers..."
cp src/app.py /opt/pocsag/app.py  # Directement dans /opt/pocsag/ pour correspondre au service
cp src/index.html /var/www/html/  # index.html maintenant dans src/
cp config/nginx.conf /etc/nginx/sites-available/pocsag-monitor
cp config/pocsag.service /etc/systemd/system/  # Utilise le bon nom de fichier
cp config/config.json.example /opt/pocsag/

echo "🔗 Configuration Nginx..."
ln -sf /etc/nginx/sites-available/pocsag-monitor /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t  # Test de la config

echo "👤 Création utilisateur pocsag..."
useradd -r -s /bin/false pocsag || true
chown -R pocsag:pocsag /opt/pocsag
chown pocsag:pocsag /var/www/html/

echo "🔄 Activation des services..."
systemctl daemon-reload
systemctl enable pocsag
systemctl enable nginx

echo "🎯 Démarrage des services..."
systemctl restart nginx
systemctl start pocsag

echo "✅ Installation terminée !"
echo ""
echo "🌐 Interface web : http://$(hostname -I | awk '{print $1}')"
echo "📊 Status service : systemctl status pocsag"
echo "📝 Logs temps réel : journalctl -u pocsag -f"
echo ""
echo "⚠️  N'oubliez pas de :"
echo "   1. Configurer Discord/Telegram dans l'interface"
echo "   2. Ajouter vos alias RIC"
echo "   3. Tester la réception SDR"