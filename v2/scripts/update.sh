#!/bin/bash
set -euo pipefail
export PATH="$PATH:/usr/sbin:/sbin:/usr/local/sbin"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()  { echo -e "${GREEN}[OK]${NC} $1"; }
err() { echo -e "${RED}[ERREUR]${NC} $1"; }
info(){ echo -e "${BLUE}[INFO]${NC} $1"; }
warn(){ echo -e "${YELLOW}[ATTENTION]${NC} $1"; }

V2_DIR="/opt/pocsag/v2"
BACKUP_DIR="$V2_DIR/backups"

if [[ $EUID -ne 0 ]]; then err "root requis (sudo)"; exit 1; fi

# Trouver le repo git : chemins connus + remontee des parents du script
find_repo_root() {
    local d
    for d in "$(pwd)" "/root/pocsag" "/home/pocsag/pocsag" "/opt/pocsag"; do
        if [ -d "$d/.git" ]; then echo "$d"; return 0; fi
    done
    local s="$(cd "$(dirname "$0")" && pwd)"
    while [ "$s" != "/" ]; do
        if [ -d "$s/.git" ]; then echo "$s"; return 0; fi
        s="$(dirname "$s")"
    done
    return 1
}

REPO_DIR="$(find_repo_root)" || REPO_DIR="/root/pocsag"
info "Depot git: $REPO_DIR"

if [ -d "$REPO_DIR/.git" ]; then
    info "Pull du depot..."
    cd "$REPO_DIR"
    git fetch origin 2>&1 | tail -1 || true
    git pull --ff-only 2>&1 | tail -3 || git reset --hard origin/main 2>&1 | tail -1 || true
fi

info "Creation de la sauvegarde..."
mkdir -p "$BACKUP_DIR"
TS=$(date +%Y%m%d_%H%M%S)
for f in "$V2_DIR/backend/app" "$V2_DIR/frontend" "$V2_DIR/config"; do
    [ -d "$f" ] && cp -r "$f" "$BACKUP_DIR/backup_$TS/" 2>/dev/null || true
done
ok "Sauvegarde: backup_$TS"

systemctl stop pocsag 2>/dev/null || true

info "Copie des fichiers..."
SRC_DIR="$REPO_DIR"
if [ ! -f "$SRC_DIR/v2/backend/app/main.py" ]; then
    SRC_DIR="/root/pocsag"
fi
if [ ! -f "$SRC_DIR/v2/backend/app/main.py" ]; then
    err "Source introuvable (main.py manquant dans $SRC_DIR)"
    systemctl start pocsag 2>/dev/null || true
    exit 1
fi

rm -rf "$V2_DIR/backend/app" "$V2_DIR/frontend" "$V2_DIR/config"
mkdir -p "$V2_DIR/backend/app" "$V2_DIR/frontend" "$V2_DIR/config"
cp -r "$SRC_DIR/v2/backend/app/"* "$V2_DIR/backend/app/"
cp -r "$SRC_DIR/v2/frontend/"* "$V2_DIR/frontend/"
cp "$SRC_DIR/v2/config/pocsag.service" "$V2_DIR/config/pocsag.service"
cp "$SRC_DIR/v2/config/nginx.conf" "$V2_DIR/config/nginx.conf"

info "Dependances Python..."
[ -f "$V2_DIR/.venv/bin/pip" ] && "$V2_DIR/.venv/bin/pip" install -r "$SRC_DIR/v2/backend/requirements.txt" --quiet --upgrade

info "Nginx..."
cp "$V2_DIR/config/nginx.conf" /etc/nginx/sites-available/pocsag-monitor
nginx -t 2>&1 && systemctl reload nginx || warn "Test nginx echoue"

info "Redemarrage du service..."
cp "$V2_DIR/config/pocsag.service" /etc/systemd/system/pocsag.service
systemctl daemon-reload
systemctl start pocsag
sleep 2

if systemctl is-active --quiet pocsag; then
    ok "Service POCSAG v2 redemarre"
else
    warn "Service inactif — rollback: cp -r $BACKUP_DIR/backup_$TS/app $V2_DIR/backend/ && systemctl restart pocsag"
fi

VERSION=$(cat "$SRC_DIR/VERSION" 2>/dev/null || echo "?")
echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Mise a jour terminee v$VERSION        ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"