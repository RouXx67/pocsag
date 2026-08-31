#!/bin/bash
#
# POCSAG Monitor - Script d'installation automatique
# Usage: sudo bash install.sh
#

set -e
export PATH="$PATH:/usr/sbin:/sbin:/usr/local/sbin"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

nginx_bin() {
    if command -v nginx >/dev/null 2>&1; then command -v nginx
    elif [ -x /usr/sbin/nginx ]; then echo /usr/sbin/nginx
    elif [ -x /sbin/nginx ]; then echo /sbin/nginx
    else echo nginx
    fi
}

print_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
print_err() { echo -e "${RED}[ERREUR]${NC} $1"; }
print_info() { echo -e "${YELLOW}[INFO]${NC} $1"; }

clear
echo "========================================="
echo "  POCSAG Monitor - Installation"
echo "========================================="
echo ""

# Vérification root
if [ "$EUID" -ne 0 ]; then
  print_err "Ce script doit etre execute en root (sudo)"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Mise à jour système
print_info "Mise a jour des paquets..."
apt update -y 2>&1 | tail -1 || true

# Installation dépendances système
print_info "Installation des dependances systeme..."
apt install -y rtl-sdr multimon-ng python3 python3-pip nginx git curl wget 2>&1 | tail -5 || true

# S'assurer que nginx est bien installe
if ! command -v nginx >/dev/null 2>&1; then
  print_info "Installation de Nginx (fallback)..."
  apt install -y nginx 2>&1 | tail -3 || true
fi

if command -v nginx >/dev/null 2>&1; then
  print_ok "Nginx disponible : $(nginx -v 2>&1)"
else
  echo -e "${YELLOW}[WARNING] Nginx non disponible - interface web limitee${NC}"
fi

# Installation module Python requests (Debian 13 / Python 3.13)
print_info "Installation du module Python requests..."
if apt install -y python3-requests 2>/dev/null; then
  print_ok "Module Python requests installe via apt"
elif pip3 install --break-system-packages requests 2>/dev/null; then
  print_ok "Module Python requests installe via pip --break-system-packages"
elif pip3 install requests 2>/dev/null; then
  print_ok "Module Python requests installe via pip"
else
  echo -e "${YELLOW}[WARNING] Echec installation Python requests automatique${NC}"
  echo "Vous pouvez installer manuellement : pip3 install requests"
fi

# Vérification installation
if python3 -c "import requests" 2>/dev/null; then
  print_ok "Module Python requests verifie avec succes"
else
  print_err "Module Python requests non disponible"
  echo "Certaines fonctionnalites Telegram/Discord peuvent etre limitees"
fi

# Blacklist des modules kernel DVB / RTL (sinon rtl_fm ne peut pas ouvrir le dongle)
print_info "Blacklist des modules kernel RTL-SDR..."
if [ ! -f /etc/modprobe.d/blacklist-rtlsdr.conf ]; then
  cat > /etc/modprobe.d/blacklist-rtlsdr.conf << 'EOF'
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
EOF
  print_ok "Modules kernel blacklist dans /etc/modprobe.d/blacklist-rtlsdr.conf"
else
  print_ok "Blacklist RTL-SDR deja present"
fi
modprobe -r dvb_usb_rtl28xxu rtl2832 rtl2830 2>/dev/null || true

echo ""
echo "========================================="
echo "  Deploiement des fichiers"
echo "========================================="
echo ""

# Création des répertoires
print_info "Creation des repertoires..."
mkdir -p /opt/pocsag
mkdir -p /var/www/html
mkdir -p /var/log/pocsag
mkdir -p /etc/nginx/sites-available
mkdir -p /etc/nginx/sites-enabled
chown -R www-data:www-data /var/www/html 2>/dev/null || true
chmod 755 /opt/pocsag 2>/dev/null || true
chmod 755 /var/log/pocsag 2>/dev/null || true

# Installation des fichiers
print_info "Installation des fichiers applicatifs..."
if [ -f "$SCRIPT_DIR/src/app.py" ]; then
  cp "$SCRIPT_DIR/src/app.py" /opt/pocsag/app.py
  chmod 644 /opt/pocsag/app.py
  print_ok "app.py -> /opt/pocsag/app.py"
else
  print_err "Fichier src/app.py introuvable dans $SCRIPT_DIR"
fi

if [ -f "$SCRIPT_DIR/src/index.html" ]; then
  cp "$SCRIPT_DIR/src/index.html" /var/www/html/index.html
  chown www-data:www-data /var/www/html/index.html 2>/dev/null || true
  chmod 644 /var/www/html/index.html 2>/dev/null || true
  print_ok "index.html -> /var/www/html/index.html"
else
  print_err "Fichier src/index.html introuvable"
fi

# Config par défaut
if [ -f "$SCRIPT_DIR/config/config.json.example" ]; then
  if [ ! -f "/opt/pocsag/config.json" ]; then
    cp "$SCRIPT_DIR/config/config.json.example" /opt/pocsag/config.json
    chmod 644 /opt/pocsag/config.json
    print_ok "config.json cree depuis config.json.example"
  else
    print_info "config.json deja present (conserve)"
    # Mettre a disposition l'exemple a jour
    cp "$SCRIPT_DIR/config/config.json.example" /opt/pocsag/config.json.example 2>/dev/null || true
  fi
fi

# data.json initial
if [ ! -f "/var/www/html/data.json" ]; then
  echo "[]" > /var/www/html/data.json
  chown www-data:www-data /var/www/html/data.json 2>/dev/null || true
  chmod 664 /var/www/html/data.json 2>/dev/null || true
  print_ok "data.json initialise"
fi
# S'assurer que data.json est accessible en ecriture pour app.py (User=root)
chmod 666 /var/www/html/data.json 2>/dev/null || chmod 664 /var/www/html/data.json || true

# Configuration Nginx
print_info "Configuration de Nginx..."
if [ -f "$SCRIPT_DIR/config/nginx.conf" ]; then
  cp "$SCRIPT_DIR/config/nginx.conf" /etc/nginx/sites-available/pocsag-monitor
  print_ok "nginx.conf -> /etc/nginx/sites-available/pocsag-monitor"
else
  # Fallback inline si config/nginx.conf absent
  cat > /etc/nginx/sites-available/pocsag-monitor << 'EOFNGINX'
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
EOFNGINX
  print_ok "nginx.conf genere (fallback)"
fi

# Activation du site nginx
print_info "Activation du site Nginx..."
ln -sf /etc/nginx/sites-available/pocsag-monitor /etc/nginx/sites-enabled/pocsag-monitor
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

# Test configuration nginx
print_info "Test configuration Nginx..."
NGINX_BIN="$(nginx_bin)"
if $NGINX_BIN -t 2>&1; then
  print_ok "Configuration Nginx valide"
else
  echo -e "${YELLOW}[WARNING] Probleme de configuration Nginx - verification manuelle requise${NC}"
  $NGINX_BIN -t 2>&1 || true
fi

# Redémarrage nginx
print_info "Redemarrage Nginx..."
if systemctl restart nginx 2>/dev/null; then
  print_ok "Nginx redemarre via systemctl"
else
  # Fallback si systemd non disponible ou service non actif
  nginx -s reload 2>/dev/null || nginx 2>/dev/null || true
  print_info "Nginx reload tente (fallback)"
fi

if systemctl is-active --quiet nginx 2>/dev/null; then
  print_ok "Nginx actif"
else
  # Verif alternative
  if pgrep nginx >/dev/null 2>&1; then
    print_ok "Nginx actif (pgrep)"
  else
    echo -e "${YELLOW}[WARNING] Nginx non actif - interface web peut etre limitee${NC}"
  fi
fi

# Service systemd pocsag
print_info "Installation du service systemd pocsag..."
if [ -f "$SCRIPT_DIR/config/pocsag.service" ]; then
  cp "$SCRIPT_DIR/config/pocsag.service" /etc/systemd/system/pocsag.service
  chmod 644 /etc/systemd/system/pocsag.service
  print_ok "pocsag.service -> /etc/systemd/system/pocsag.service"
  if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload
    systemctl enable pocsag 2>/dev/null || true
    print_ok "Service pocsag active (enable)"
    # Ne pas redemarrer automatiquement ici : laisse l'utilisateur controler, mais tenter un restart si deja actif
    if systemctl is-active --quiet pocsag 2>/dev/null; then
      systemctl restart pocsag 2>/dev/null || true
      print_ok "Service pocsag redemarre"
    else
      print_info "Service pocsag installe - demarrage avec: systemctl start pocsag"
    fi
  fi
else
  print_err "Fichier config/pocsag.service introuvable"
fi

# Optionnel : garder pocsag-monitor.service comme alias si present
if [ -f "$SCRIPT_DIR/config/pocsag-monitor.service" ] && [ ! -f "/etc/systemd/system/pocsag-monitor.service" ]; then
  cp "$SCRIPT_DIR/config/pocsag-monitor.service" /etc/systemd/system/pocsag-monitor.service 2>/dev/null || true
fi

echo ""
echo "========================================="
echo "  Installation terminee !"
echo "========================================="
echo ""
print_info "Interface web : http://$(hostname -I 2>/dev/null | awk '{print $1}')"
print_info "Service pocsag : systemctl status pocsag"
print_info "Logs temps reel : journalctl -u pocsag -f"
print_info "Config : /opt/pocsag/config.json"
echo ""
echo -e "${YELLOW}Etapes suivantes :${NC}"
echo "  1. Configurer Discord/Telegram dans l'interface web (onglet Settings)"
echo "  2. Ajouter vos alias RIC"
echo "  3. Tester la reception : rtl_test -t"
echo "  4. Demarrer le service si non actif : systemctl start pocsag"
