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

# Trouver le repo git : d'abord par .git dans parents, puis chemins connus
find_repo_root() {
    local dir
    for dir in "$(pwd)" "/home/pocsag/pocsag" "/root/pocsag" "/opt/pocsag"; do
        if [ -d "$dir/.git" ]; then
            echo "$dir"
            return 0
        fi
    done
    # Remonter depuis le script
    local script_dir
    script_dir="$(cd "$(dirname "$0")" && pwd)"
    while [ "$script_dir" != "/" ]; do
        if [ -d "$script_dir/.git" ]; then
            echo "$script_dir"
            return 0
        fi
        script_dir="$(dirname "$script_dir")"
    done
    return 1
}

REPO_DIR="$(find_repo_root)" || {
    warn "D\u00e9p\u00f4t Git introuvable, utilisation des fichiers locaux"
    REPO_DIR="/home/pocsag/pocsag"
}

info "R\u00e9pertoire du d\u00e9p\u00f4t: $REPO_DIR"

if [ -d "$REPO_DIR/.git" ]; then
    info "Mise \u00e0 jour du d\u00e9p\u00f4t Git..."
    cd "$REPO_DIR"
    git fetch origin 2>&1 | tail -1 || true
    git pull --ff-only 2>&1 | tail -3 || git reset --hard origin/main 2>&1 | tail -1 || true
else
    warn "D\u00e9p\u00f4t .git introuvable, on continue sans pull"
fi

info "Cr\u00e9ation de la sauvegarde..."
mkdir -p "$BACKUP_DIR"
TS=$(date +%Y%m%d_%H%M%S)
for f in "$V2_DIR/backend/app" "$V2_DIR/frontend" "$V2_DIR/config"; do
    [ -d "$f" ] && cp -r "$f" "$BACKUP_DIR/backup_$TS/" 2>/dev/null || true
done
ok "Sauvegarde cr\u00e9\u00e9e: backup_$TS"

systemctl stop pocsag 2>/dev/null || true

info "Copie des fichiers..."
rm -rf "$V2_DIR/backend/app" "$V2_DIR/frontend" "$V2_DIR/config"
mkdir -p "$V2_DIR/backend/app" "$V2_DIR/frontend" "$V2_DIR/config"

# Essayer REPO_DIR d'abord, puis le script_dir, puis fallback
SRC_DIR="$REPO_DIR"
if [ ! -f "$SRC_DIR/v2/backend/app/main.py" ]; then
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    SRC_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi
if [ ! -f "$SRC_DIR/v2/backend/app/main.py" ]; then
    SRC_DIR="/home/pocsag/pocsag"
fi

info "Source des fichiers: $SRC_DIR"

cp -r "$SRC_DIR/v2/backend/app/"* "$V2_DIR/backend/app/"
cp -r "$SRC_DIR/v2/frontend/"* "$V2_DIR/frontend/"
cp "$SRC_DIR/v2/config/pocsag.service" "$V2_DIR/config/pocsag.service"
cp "$SRC_DIR/v2/config/nginx.conf" "$V2_DIR/config/nginx.conf"

info "Mise \u00e0 jour des d\u00e9pendances Python..."
[ -f "$V2_DIR/.venv/bin/pip" ] && "$V2_DIR/.venv/bin/pip" install -r "$SRC_DIR/v2/backend/requirements.txt" --quiet --upgrade

info "Mise \u00e0 jour Nginx..."
cp "$V2_DIR/config/nginx.conf" /etc/nginx/sites-available/pocsag-monitor
nginx -t 2>&1 && systemctl reload nginx || warn "Test nginx \u00e9chou\u00e9"

info "Red\u00e9marrage du service..."
cp "$V2_DIR/config/pocsag.service" /etc/systemd/system/pocsag.service
systemctl daemon-reload
systemctl start pocsag
sleep 2

if systemctl is-active --quiet pocsag; then
    ok "Service POCSAG v2 red\u00e9marr\u00e9"
else
    warn "Service inactif — rollback: cp -r $BACKUP_DIR/backup_$TS/app $V2_DIR/backend/ && systemctl restart pocsag"
fi

VERSION=$(cat "$SRC_DIR/VERSION" 2>/dev/null || echo "?")
echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Mise \u00e0 jour termin\u00e9e v$VERSION       ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"