#!/bin/bash
set -euo pipefail
export PATH="$PATH:/usr/sbin:/sbin:/usr/local/sbin"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()  { echo -e "${GREEN}[OK]${NC} $1"; }
err() { echo -e "${RED}[ERREUR]${NC} $1"; }
info(){ echo -e "${BLUE}[INFO]${NC} $1"; }
warn(){ echo -e "${YELLOW}[ATTENTION]${NC} $1"; }

find_repo_root() {
    local dir
    for dir in "$(pwd)" "/home/pocsag/pocsag" "/root/pocsag" "/opt/pocsag"; do
        if [ -d "$dir/.git" ]; then echo "$dir"; return 0; fi
    done
    local d="$(cd "$(dirname "$0")" && pwd)"
    while [ "$d" != "/" ]; do
        if [ -d "$d/.git" ]; then echo "$d"; return 0; fi
        d="$(dirname "$d")"
    done
    return 1
}

REPO_DIR="$(find_repo_root)" || REPO_DIR="/home/pocsag/pocsag"

if [[ $EUID -ne 0 ]]; then err "root requis (sudo)"; exit 1; fi

echo -e "${BLUE}╔═══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     POCSAG Monitor v2 - Installation ${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════╝${NC}"

if [ -d "$REPO_DIR/.git" ]; then
    info "Mise à jour du dépôt Git..."
    cd "$REPO_DIR"
    git fetch origin 2>&1 | tail -1 || true
    git pull --ff-only 2>&1 | tail -3 || git reset --hard origin/main 2>&1 | tail -1 || true
fi

info "Installation des dépendances système..."
apt update -y 2>&1 | tail -1 || warn "apt update ignoré"
apt install -y rtl-sdr multimon-ng python3 python3-pip python3-venv nginx git 2>&1 | tail -3 || warn "apt install ignoré"

info "Création des dossiers..."
mkdir -p /opt/pocsag/v2/data

info "Installation des dépendances Python..."
python3 -m venv /opt/pocsag/v2/.venv
/opt/pocsag/v2/.venv/bin/pip install -r "$REPO_DIR/v2/backend/requirements.txt" --quiet

info "Copie des fichiers..."
rm -rf /opt/pocsag/v2/backend /opt/pocsag/v2/frontend /opt/pocsag/v2/config /opt/pocsag/v2/scripts
for d in v2/backend v2/frontend v2/config v2/scripts; do
    cp -r "$REPO_DIR/$d" "/opt/pocsag/$d"
done
chmod 755 /opt/pocsag/v2/data

info "Configuration Nginx..."
cp /opt/pocsag/v2/config/nginx.conf /etc/nginx/sites-available/pocsag-monitor
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/pocsag-monitor /etc/nginx/sites-enabled/
if nginx -t 2>&1; then systemctl reload nginx; else warn "Test nginx échoué"; fi

info "Installation du service systemd..."
cp /opt/pocsag/v2/config/pocsag.service /etc/systemd/system/pocsag.service
systemctl daemon-reload
systemctl enable pocsag
systemctl start pocsag

sleep 2
if systemctl is-active --quiet pocsag; then
    ok "Service POCSAG v2 actif"
else
    warn "Service inactif, vérifiez: journalctl -u pocsag -n 30"
fi
if systemctl is-active --quiet nginx; then ok "Nginx actif"; else warn "Nginx inactif"; fi

IP=$(hostname -I | awk '{print $1}')
echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Installation terminée !              ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
echo -e "🌐 Interface : ${BLUE}http://$IP${NC}"
echo -e "🔑 Mot de passe par défaut : ${YELLOW}admin${NC}"
echo -e "📝 Logs : ${YELLOW}journalctl -u pocsag -f${NC}"