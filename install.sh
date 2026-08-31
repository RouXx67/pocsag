#!/bin/bash
#
# POCSAG Monitor Pro - Script d'installation automatique
# Usage: sudo bash install.sh
#

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
print_err() { echo -e "${RED}[ERREUR]${NC} $1"; }
print_info() { echo -e "${NC}[$1] $2"; }

clear
echo "========================================="
echo "  POCSAG Monitor Pro - Installation"
echo "========================================="
echo ""

# Vérification root
if [ "$EUID" -ne 0 ]; then
  print_err "Ce script doit être exécuté en root (sudo)"
  exit 1
fi

# Mise à jour système
print_info "MAJ" "Mise à jour des paquets..."
apt update -y 2>&1 | tail -1

# Installation dépendances système
print_info "DEPS" "Installation des dépendances système..."
apt install -y rtl-sdr multimon-ng python3 python3-pip nginx git curl wget 2>&1 | tail -3

# Installation module Python requests
print_info "PYTHON" "Installation du module Python requests..."

# Essayer d'abord apt (recommandé pour Python 3.13+)
if apt install -y python3-requests 2>/dev/null; then
  print_ok "Module Python requests installé via apt"
# Essayer pip avec --break-system-packages
elif pip3 install --break-system-packages requests 2>/dev/null; then
  print_ok "Module Python requests installé via pip --break-system-packages"
# Essayer pip standard
elif pip3 install requests 2>/dev/null; then
  print_ok "Module Python requests installé via pip standard"
# Échoué - message d'avertissement
else
  print_warning "Échec installation Python requests automatique"
  print_info "INFO" "Vous pouvez installer manuellement : pip3 install requests"
fi

# Vérification installation
if python3 -c "import requests" 2>/dev/null; then
  print_ok "Module Python requests vérifié avec succès"
else
  print_err "Module Python requests non disponible"
  print_info "INFO" "Certaines fonctionnalités Telegram/Discord peuvent être limitées"
fi

echo ""
echo "========================================="
echo "  Installation terminée !"
echo "========================================="
echo ""

# Création des répertoires
print_info "REP" "Création des répertoires..."
mkdir -p /opt/pocsag
mkdir -p /var/www/html
mkdir -p /var/log/pocsag
chown -R www-data:www-data /var/www/html
chmod 755 /opt/pocsag
chmod 755 /var/log/pocsag

# Installation des fichiers
print_info "FICHIER" "Installation des fichiers..."
cp src/app.py /opt/pocsag/app.py 2>/dev/null || true
cp src/index.html /var/www/html/index.html 2>/dev/null || true

# Configuration de Nginx
print_info "NGINX" "Configuration de Nginx..."
cat > /etc/nginx/sites-available/pocsag-monitor << 'EOF'
server {
    listen 80;
    server_name localhost;
    
    location / {
        root /var/www/html;
        index index.html;
        try_files $uri $uri/ =404;
    }
    
    location /api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /data.json {
        root /var/www/html;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }
}
EOF

# Activation du site nginx
print_info "NGINX2" "Activation du site..."
ln -sf /etc/nginx/sites-available/pocsag-monitor /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test configuration nginx
print_info "NGINX3" "Test configuration Nginx..."
if nginx -t; then
  print_ok "Configuration Nginx valide"
else
  print_warning "Problème de configuration Nginx - vérification manuelle requise"
fi

# Redémarrage nginx
print_info "NGINX4" "Redémarrage Nginx..."
systemctl restart nginx 2>/dev/null || nginx

# Vérification finale
if systemctl is-active --quiet nginx 2>/dev/null; then
  print_ok "Nginx actif"
else
  print_warning "Nginx non actif - interface web peut être limitée"
fi

print_info "WEB" "Interface : http://$(hostname -I | awk '{print $1}')"
print_info "SERVICE" "Service : systemctl status pocsag"