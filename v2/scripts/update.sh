#!/bin/bash
set -euo pipefail
export PATH="$PATH:/usr/sbin:/sbin:/usr/local/sbin"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()  { echo -e "${GREEN}[OK]${NC} $1"; }
err() { echo -e "${RED}[ERREUR]${NC} $1"; }
info(){ echo -e "${BLUE}[INFO]${NC} $1"; }
warn(){ echo -e "${YELLOW}[ATTENTION]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
V2_DIR="/opt/pocsag/v2"
BACKUP_DIR="$V2_DIR/backups"

if [[ $EUID -ne 0 ]]; then err "root requis (sudo)"; exit 1; fi

info "Mise à jour du dépôt Git..."
cd "$REPO_DIR"
git fetch origin 2>&1 | tail -1 || true
git pull --ff-only 2>&1 | tail -3 || git reset --hard origin/main 2>&1 | tail -1 || true

info "Création de la sauvegarde..."
mkdir -p "$BACKUP_DIR"
TS=$(date +%Y%m%d_%H%M%S)
for f in "$V2_DIR/backend/app" "$V2_DIR/frontend" "$V2_DIR/config"; do
    [ -d "$f" ] && cp -r "$f" "$BACKUP_DIR/backup_$TS/" 2>/dev/null || true
done
ok "Sauvegarde créée: backup_$TS"

systemctl stop pocsag 2>/dev/null || true

info "Copie des fichiers..."
ensure_dir() { mkdir -p "$(dirname "$1")"; }

ensure_dir "$V2_DIR/backend/app"
cp -r "$REPO_DIR/v2/backend/app/"* "$V2_DIR/backend/app/"
ensure_dir "$V2_DIR/frontend"
cp -r "$REPO_DIR/v2/frontend/"* "$V2_DIR/frontend/"
ensure_dir "$V2_DIR/config"
cp "$REPO_DIR/v2/config/pocsag.service" "$V2_DIR/config/pocsag.service"
cp "$REPO_DIR/v2/config/nginx.conf" "$V2_DIR/config/nginx.conf"

info "Mise à jour des dépendances Python..."
[ -f "$V2_DIR/.venv/bin/pip" ] && "$V2_DIR/.venv/bin/pip" install -r "$REPO_DIR/v2/backend/requirements.txt" --quiet --upgrade

info "Mise à jour Nginx..."
cp "$V2_DIR/config/nginx.conf" /etc/nginx/sites-available/pocsag-monitor
nginx -t 2>&1 && systemctl reload nginx || warn "Test nginx échoué"

info "Redémarrage du service..."
cp "$V2_DIR/config/pocsag.service" /etc/systemd/system/pocsag.service
systemctl daemon-reload
systemctl start pocsag
sleep 2

if systemctl is-active --quiet pocsag; then
    ok "Service POCSAG v2 redémarré"
else
    warn "Service inactif — rollback possible:"
    warn "  cp -r $BACKUP_DIR/backup_$TS/app $V2_DIR/backend/ && systemctl restart pocsag"
fi

VERSION=$(cat "$REPO_DIR/VERSION" 2>/dev/null || echo "?")
echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Mise à jour terminée v$VERSION         ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"