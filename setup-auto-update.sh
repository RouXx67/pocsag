#!/bin/bash
#
# Configuration des mises à jour automatiques POCSAG Monitor
# Usage: sudo bash setup-auto-update.sh
#

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════╗"
    echo "║     Configuration Auto-Update         ║"
    echo "║       POCSAG Monitor              ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
}

# Vérification root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "Ce script doit être exécuté en root (sudo)"
        exit 1
    fi
}

# Menu de configuration
show_menu() {
    echo -e "\n${BLUE}Options de mise à jour automatique :${NC}"
    echo "1) Vérification quotidienne à 03:00 (recommandé)"
    echo "2) Vérification hebdomadaire (dimanche 02:00)"
    echo "3) Vérification personnalisée"
    echo "4) Désactiver les mises à jour automatiques"
    echo "5) Afficher la configuration actuelle"
    echo "6) Quitter"
    
    read -p "Votre choix [1-6] : " choice
    
    case $choice in
        1) setup_daily_update ;;
        2) setup_weekly_update ;;
        3) setup_custom_update ;;
        4) disable_auto_update ;;
        5) show_current_config ;;
        6) exit 0 ;;
        *) 
            print_error "Choix invalide"
            show_menu
            ;;
    esac
}

# Configuration quotidienne
setup_daily_update() {
    print_status "Configuration des mises à jour quotidiennes à 03:00..."
    
    # Création du cron job
    create_cron_job "0 3 * * *" "Mise à jour quotidienne à 03:00"
    
    print_success "Mises à jour quotidiennes configurées !"
    show_next_execution
}

# Configuration hebdomadaire
setup_weekly_update() {
    print_status "Configuration des mises à jour hebdomadaires (dimanche 02:00)..."
    
    # Création du cron job
    create_cron_job "0 2 * * 0" "Mise à jour hebdomadaire (dimanche 02:00)"
    
    print_success "Mises à jour hebdomadaires configurées !"
    show_next_execution
}

# Configuration personnalisée
setup_custom_update() {
    echo -e "\n${BLUE}Configuration personnalisée${NC}"
    echo "Format cron : minute heure jour mois jour_semaine"
    echo "Exemples :"
    echo "  0 2 * * *     - Tous les jours à 02:00"
    echo "  30 1 * * 1    - Tous les lundis à 01:30"
    echo "  0 4 1 * *     - Le 1er de chaque mois à 04:00"
    echo ""
    
    read -p "Expression cron : " cron_expression
    read -p "Description : " description
    
    if validate_cron "$cron_expression"; then
        create_cron_job "$cron_expression" "$description"
        print_success "Configuration personnalisée appliquée !"
        show_next_execution
    else
        print_error "Expression cron invalide"
        setup_custom_update
    fi
}

# Validation de l'expression cron
validate_cron() {
    local cron="$1"
    # Validation basique (5 champs séparés par des espaces)
    if [[ $cron =~ ^[0-9*,/-]+[[:space:]]+[0-9*,/-]+[[:space:]]+[0-9*,/-]+[[:space:]]+[0-9*,/-]+[[:space:]]+[0-9*,/-]+$ ]]; then
        return 0
    else
        return 1
    fi
}

# Création du job cron
create_cron_job() {
    local cron_time="$1"
    local description="$2"
    local current_dir=$(pwd)
    
    # Suppression de l'ancien job s'il existe
    crontab -l 2>/dev/null | grep -v "pocsag.*auto-update" | crontab - 2>/dev/null || true
    
    # Ajout du nouveau job
    (crontab -l 2>/dev/null || true; echo "$cron_time cd $current_dir && bash auto-update.sh # POCSAG Auto-Update: $description") | crontab -
    
    # Vérification
    if crontab -l | grep -q "auto-update.sh"; then
        print_success "Job cron créé avec succès"
    else
        print_error "Erreur lors de la création du job cron"
        return 1
    fi
    
    # S'assurer que cron est activé
    systemctl enable cron 2>/dev/null || systemctl enable crond 2>/dev/null || true
    systemctl start cron 2>/dev/null || systemctl start crond 2>/dev/null || true
}

# Désactivation des mises à jour automatiques
disable_auto_update() {
    print_status "Désactivation des mises à jour automatiques..."
    
    # Suppression du job cron
    crontab -l 2>/dev/null | grep -v "pocsag.*auto-update" | crontab - 2>/dev/null || true
    
    print_success "Mises à jour automatiques désactivées"
}

# Affichage de la configuration actuelle
show_current_config() {
    echo -e "\n${BLUE}Configuration actuelle :${NC}"
    
    # Vérification du cron job
    if crontab -l 2>/dev/null | grep -q "auto-update.sh"; then
        echo -e "${GREEN}✅ Mises à jour automatiques activées${NC}"
        echo ""
        echo "Job cron actuel :"
        crontab -l | grep "auto-update.sh" | while read line; do
            echo "  $line"
        done
        
        show_next_execution
    else
        echo -e "${YELLOW}⚠️  Mises à jour automatiques non configurées${NC}"
    fi
    
    # Vérification des logs
    if [ -f "/var/log/pocsag/auto-update.log" ]; then
        echo -e "\n${BLUE}Dernières exécutions :${NC}"
        tail -5 /var/log/pocsag/auto-update.log | while read line; do
            echo "  $line"
        done
    fi
    
    echo ""
}

# Affichage de la prochaine exécution
show_next_execution() {
    if command -v python3 &> /dev/null; then
        echo -e "\n${BLUE}Prochaine exécution estimée :${NC}"
        # Calcul approximatif avec Python (si disponible)
        python3 -c "
import datetime
from datetime import timedelta
import subprocess
import re

try:
    cron_output = subprocess.check_output(['crontab', '-l'], stderr=subprocess.DEVNULL).decode()
    for line in cron_output.split('\n'):
        if 'auto-update.sh' in line:
            parts = line.split()[:5]
            print(f'  Expression cron: {\" \".join(parts)}')
            break
except:
    pass

print(f'  Heure actuelle: {datetime.datetime.now().strftime(\"%Y-%m-%d %H:%M:%S\")}')
"
    fi
}

# Configuration des notifications email (optionnel)
setup_email_notifications() {
    echo -e "\n${BLUE}Configuration des notifications email (optionnel)${NC}"
    
    read -p "Adresse email pour les notifications (vide pour ignorer) : " email
    
    if [ -n "$email" ]; then
        # Installation de mailutils si nécessaire
        if ! command -v mail &> /dev/null; then
            print_status "Installation de mailutils pour les notifications email..."
            apt update && apt install -y mailutils
        fi
        
        # Configuration dans le script auto-update
        sed -i "s/NOTIFICATION_EMAIL=\"\"/NOTIFICATION_EMAIL=\"$email\"/" auto-update.sh
        
        print_success "Notifications email configurées pour : $email"
    else
        print_status "Notifications email ignorées"
    fi
}

# Test des mises à jour automatiques
test_auto_update() {
    print_status "Test du système de mise à jour automatique..."
    
    if [ ! -f "auto-update.sh" ]; then
        print_error "Script auto-update.sh non trouvé !"
        return 1
    fi
    
    # Test d'exécution
    print_status "Exécution du test..."
    if timeout 30s bash auto-update.sh; then
        print_success "Test réussi !"
    else
        print_warning "Le test a pris plus de 30 secondes ou a échoué"
    fi
    
    # Vérification des logs
    if [ -f "/var/log/pocsag/auto-update.log" ]; then
        echo -e "\n${BLUE}Dernières lignes du log :${NC}"
        tail -3 /var/log/pocsag/auto-update.log
    fi
}

# Fonction principale
main() {
    print_header
    check_root
    
    # Vérification des prérequis
    if [ ! -f "auto-update.sh" ]; then
        print_error "Script auto-update.sh non trouvé dans le répertoire actuel !"
        exit 1
    fi
    
    if [ ! -f "update.sh" ]; then
        print_error "Script update.sh non trouvé dans le répertoire actuel !"
        exit 1
    fi
    
    # Configuration des notifications email
    setup_email_notifications
    
    # Menu principal
    while true; do
        show_menu
        
        echo ""
        read -p "Continuer la configuration ? (o/n) : " continue_config
        if [ "$continue_config" != "o" ] && [ "$continue_config" != "O" ]; then
            break
        fi
    done
    
    # Test final
    echo ""
    read -p "Tester le système maintenant ? (o/n) : " test_now
    if [ "$test_now" = "o" ] || [ "$test_now" = "O" ]; then
        test_auto_update
    fi
    
    echo -e "\n${GREEN}Configuration terminée !${NC}"
    echo -e "${BLUE}Pour voir les logs : tail -f /var/log/pocsag/auto-update.log${NC}"
}

# Exécution
main "$@"