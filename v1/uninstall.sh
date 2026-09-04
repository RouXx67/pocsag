#!/bin/bash
#
# POCSAG Monitor - Script de désinstallation
# Usage: sudo bash uninstall.sh
#

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${RED}"
    echo "╔═══════════════════════════════════════╗"
    echo "║        POCSAG Monitor             ║"
    echo "║      Désinstallation complète         ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
}

# Vérification root
if [[ $EUID -ne 0 ]]; then
    print_error "Ce script doit être exécuté en root (sudo)"
    exit 1
fi

print_header

# Confirmation
echo -e "${YELLOW}⚠️  Cette action va supprimer complètement POCSAG Monitor${NC}"
echo "- Services systemd"
echo "- Fichiers de configuration"
echo "- Interface web"
echo "- Logs (sauf si vous choisissez de les garder)"
echo ""
read -p "Êtes-vous sûr ? (oui/non) : " confirm

if [ "$confirm" != "oui" ]; then
    print_status "Désinstallation annulée"
    exit 0
fi

# Demander si on garde les logs
echo ""
read -p "Conserver les logs et la configuration ? (o/n) : " keep_data

print_status "Début de la désinstallation..."

# Arrêt des services
print_status "Arrêt des services..."
systemctl stop pocsag 2>/dev/null || true
systemctl disable pocsag 2>/dev/null || true

# Suppression du service systemd
print_status "Suppression du service systemd..."
rm -f /etc/systemd/system/pocsag.service
systemctl daemon-reload

# Suppression des fichiers Nginx
print_status "Suppression de la configuration Nginx..."
rm -f /etc/nginx/sites-available/pocsag-monitor
rm -f /etc/nginx/sites-enabled/pocsag-monitor

# Redémarrage nginx pour appliquer les changements
systemctl restart nginx 2>/dev/null || true

# Suppression des fichiers principaux
print_status "Suppression des fichiers d'application..."
rm -rf /opt/pocsag
rm -f /var/www/html/index.html

# Suppression conditionnelle des logs
if [ "$keep_data" != "o" ] && [ "$keep_data" != "O" ]; then
    print_status "Suppression des logs..."
    rm -rf /var/log/pocsag
    rm -f /var/www/html/data.json
else
    print_warning "Logs conservés dans /var/log/pocsag/"
fi

# Option de suppression des dépendances
echo ""
read -p "Supprimer aussi les dépendances (rtl-sdr, multimon-ng) ? (o/n) : " remove_deps

if [ "$remove_deps" = "o" ] || [ "$remove_deps" = "O" ]; then
    print_status "Suppression des dépendances..."
    if command -v apt &> /dev/null; then
        apt remove --purge -y rtl-sdr multimon-ng
        apt autoremove -y
    elif command -v yum &> /dev/null; then
        yum remove -y rtl-sdr
    fi
    
    # Suppression des dépendances Python
    pip3 uninstall -y requests 2>/dev/null || true
else
    print_warning "Dépendances conservées"
fi

print_success "Désinstallation terminée !"

echo -e "\n${BLUE}Résumé :${NC}"
echo "✅ Service POCSAG supprimé"
echo "✅ Configuration Nginx supprimée"  
echo "✅ Fichiers d'application supprimés"

if [ "$keep_data" != "o" ] && [ "$keep_data" != "O" ]; then
    echo "✅ Logs supprimés"
else
    echo "⚠️  Logs conservés"
fi

if [ "$remove_deps" = "o" ] || [ "$remove_deps" = "O" ]; then
    echo "✅ Dépendances supprimées"
else
    echo "⚠️  Dépendances conservées"
fi

echo -e "\n${GREEN}POCSAG Monitor complètement désinstallé !${NC}"