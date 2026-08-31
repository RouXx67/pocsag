#!/bin/bash
#
# POCSAG Monitor - Script de mise à jour intelligent
# Usage: sudo bash update.sh [options]
# Options: --force, --backup-only, --check-only, --rollback
#

set -e
export PATH="$PATH:/usr/sbin:/sbin:/usr/local/sbin"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Variables globales
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="/opt/pocsag/backups"
CURRENT_DIR=$(pwd)

nginx_bin() {
    if command -v nginx >/dev/null 2>&1; then command -v nginx
    elif [ -x /usr/sbin/nginx ]; then echo /usr/sbin/nginx
    elif [ -x /sbin/nginx ]; then echo /sbin/nginx
    else echo nginx
    fi
}
FORCE_UPDATE=false
BACKUP_ONLY=false
CHECK_ONLY=false
ROLLBACK=false
UPDATE_AVAILABLE=false

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

print_update() {
    echo -e "${PURPLE}[UPDATE]${NC} $1"
}

print_header() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════╗"
    echo "║        POCSAG Monitor             ║"
    echo "║      Mise à jour intelligente         ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
}

# Gestion des arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --force)
                FORCE_UPDATE=true
                shift
                ;;
            --backup-only)
                BACKUP_ONLY=true
                shift
                ;;
            --check-only)
                CHECK_ONLY=true
                shift
                ;;
            --rollback)
                ROLLBACK=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                print_error "Option inconnue: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    echo "Usage: sudo bash update.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --force        Force la mise à jour sans confirmation"
    echo "  --backup-only  Effectue seulement une sauvegarde"
    echo "  --check-only   Vérifie seulement s'il y a des mises à jour"
    echo "  --rollback     Restaure la dernière sauvegarde"
    echo "  --help         Affiche cette aide"
    echo ""
    echo "Exemples:"
    echo "  sudo bash update.sh                    # Mise à jour interactive"
    echo "  sudo bash update.sh --check-only       # Vérification seulement"
    echo "  sudo bash update.sh --force            # Mise à jour forcée"
    echo "  sudo bash update.sh --rollback         # Restauration"
}

# Vérification des privilèges
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "Ce script doit être exécuté en root (sudo)"
        exit 1
    fi
}

# Vérification de l'installation existante
check_installation() {
    print_status "Vérification de l'installation existante..."
    
    if [ ! -f "/opt/pocsag/app.py" ]; then
        print_error "POCSAG Monitor n'est pas installé !"
        print_status "Utilisez 'sudo bash setup.sh' pour l'installer"
        exit 1
    fi
    
    if [ ! -f "/etc/systemd/system/pocsag.service" ]; then
        print_error "Service systemd non trouvé !"
        exit 1
    fi
    
    print_success "Installation existante détectée"
}

# Création du répertoire de sauvegarde
setup_backup_dir() {
    mkdir -p "$BACKUP_DIR"
    chmod 755 "$BACKUP_DIR"
}

# Sauvegarde de l'installation actuelle
create_backup() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_path="$BACKUP_DIR/backup_$timestamp"
    
    print_status "Création de la sauvegarde : $backup_path"
    
    mkdir -p "$backup_path"
    
    # Sauvegarde des fichiers critiques
    files_to_backup=(
        "/opt/pocsag/app.py"
        "/var/www/html/index.html"
        "/opt/pocsag/config.json"
        "/etc/systemd/system/pocsag.service"
        "/etc/nginx/sites-available/pocsag-monitor"
        "/var/www/html/data.json"
    )
    
    for file in "${files_to_backup[@]}"; do
        if [ -f "$file" ]; then
            local dir_name=$(dirname "$file")
            mkdir -p "$backup_path$dir_name"
            cp "$file" "$backup_path$file"
            print_status "Sauvegardé: $file"
        fi
    done
    
    # Sauvegarde des logs récents
    if [ -d "/var/log/pocsag" ]; then
        mkdir -p "$backup_path/var/log"
        cp -r /var/log/pocsag "$backup_path/var/log/"
    fi
    
    # Création d'un manifest de la sauvegarde
    cat > "$backup_path/backup_info.txt" << EOF
POCSAG Monitor - Sauvegarde
Date: $(date)
Version: $(get_current_version)
Fichiers sauvegardés: ${#files_to_backup[@]}
Taille: $(du -sh "$backup_path" | cut -f1)
EOF
    
    # Lien vers la dernière sauvegarde
    ln -sfn "$backup_path" "$BACKUP_DIR/latest"
    
    print_success "Sauvegarde créée: $backup_path"
    
    # Nettoyage des anciennes sauvegardes (garde les 5 dernières)
    cleanup_old_backups
}

# Nettoyage des anciennes sauvegardes
cleanup_old_backups() {
    local backup_count
    backup_count=$(ls -1 "$BACKUP_DIR" 2>/dev/null | grep -c "^backup_" || echo 0)
    
    if [ "$backup_count" -gt 5 ]; then
        print_status "Nettoyage des anciennes sauvegardes (garde les 5 dernières)"
        ls -1t "$BACKUP_DIR"/backup_* 2>/dev/null | tail -n +6 | xargs -r rm -rf 2>/dev/null || true
        print_success "Anciennes sauvegardes supprimées"
    fi
}

# Obtenir la version actuelle
get_current_version() {
    if [ -f "/opt/pocsag/VERSION" ]; then
        cat /opt/pocsag/VERSION
    else
        echo "inconnue"
    fi
}

# Vérifier s'il y a des mises à jour
check_for_updates() {
    print_status "Vérification des mises à jour disponibles..."
    
    # Vérification des fichiers locaux (chemins absolus via SCRIPT_DIR)
    local files_changed=false
    
    if [ -f "$SCRIPT_DIR/src/app.py" ]; then
        if ! cmp -s "$SCRIPT_DIR/src/app.py" "/opt/pocsag/app.py" 2>/dev/null; then
            print_update "app.py a des modifications"
            files_changed=true
        fi
    fi
    
    if [ -f "$SCRIPT_DIR/src/index.html" ]; then
        if ! cmp -s "$SCRIPT_DIR/src/index.html" "/var/www/html/index.html" 2>/dev/null; then
            print_update "index.html a des modifications"
            files_changed=true
        fi
    fi
    
    if [ -f "$SCRIPT_DIR/config/pocsag.service" ]; then
        if ! cmp -s "$SCRIPT_DIR/config/pocsag.service" "/etc/systemd/system/pocsag.service" 2>/dev/null; then
            print_update "pocsag.service a des modifications"
            files_changed=true
        fi
    fi
    
    if [ -f "$SCRIPT_DIR/config/nginx.conf" ]; then
        if ! cmp -s "$SCRIPT_DIR/config/nginx.conf" "/etc/nginx/sites-available/pocsag-monitor" 2>/dev/null; then
            print_update "nginx.conf a des modifications"
            files_changed=true
        fi
    fi
    
    # Vérification Git si disponible
    if [ -d ".git" ] && command -v git &> /dev/null; then
        print_status "Vérification des mises à jour Git..."
        
        # Fetch les derniers changements
        git fetch origin main 2>/dev/null || git fetch origin master 2>/dev/null || true
        
        local current_commit=$(git rev-parse HEAD)
        local remote_commit=$(git rev-parse @{u} 2>/dev/null || echo $current_commit)
        
        if [ "$current_commit" != "$remote_commit" ]; then
            print_update "Nouvelles versions disponibles sur Git"
            files_changed=true
            
            # Affichage des commits
            echo -e "\n${BLUE}Nouveaux commits :${NC}"
            git log --oneline $current_commit..$remote_commit | head -5
        fi
    fi
    
    if [ "$files_changed" = true ]; then
        UPDATE_AVAILABLE=true
        print_success "Mises à jour disponibles !"
    else
        print_success "Système à jour"
        UPDATE_AVAILABLE=false
    fi
    
    return 0
}

# Afficher un résumé des changements
show_changes_summary() {
    echo -e "\n${BLUE}═══ Résumé des changements ═══${NC}"
    
    # Comparaison des fichiers (préfixés par SCRIPT_DIR)
    files_to_check=(
        "$SCRIPT_DIR/src/app.py:/opt/pocsag/app.py:Backend Python"
        "$SCRIPT_DIR/src/index.html:/var/www/html/index.html:Interface Web"
        "$SCRIPT_DIR/config/pocsag.service:/etc/systemd/system/pocsag.service:Service systemd"
        "$SCRIPT_DIR/config/nginx.conf:/etc/nginx/sites-available/pocsag-monitor:Configuration Nginx"
    )
    
    for file_info in "${files_to_check[@]}"; do
        local src=$(echo $file_info | cut -d':' -f1)
        local dst=$(echo $file_info | cut -d':' -f2)
        local desc=$(echo $file_info | cut -d':' -f3)
        
        if [ -f "$src" ] && [ -f "$dst" ]; then
            if ! cmp -s "$src" "$dst"; then
                echo -e "🔄 ${YELLOW}$desc${NC} sera mis à jour"
                
                # Afficher quelques lignes de différences
                echo -e "   ${CYAN}Aperçu des changements :${NC}"
                diff -u "$dst" "$src" | head -10 | sed 's/^/   /' || true
                echo ""
            fi
        elif [ -f "$src" ] && [ ! -f "$dst" ]; then
            echo -e "➕ ${GREEN}$desc${NC} sera installé"
        fi
    done
}

# Mise à jour des fichiers
update_files() {
    print_status "Mise à jour des fichiers..."
    
    # Arrêt temporaire du service
    print_status "Arrêt temporaire du service POCSAG..."
    systemctl stop pocsag 2>/dev/null || true
    
    # Mise à jour app.py
    if [ -f "$SCRIPT_DIR/src/app.py" ]; then
        cp "$SCRIPT_DIR/src/app.py" "/opt/pocsag/app.py"
        chown root:root /opt/pocsag/app.py 2>/dev/null || true
        chmod 644 /opt/pocsag/app.py
        print_success "app.py mis à jour"
    fi
    
    # Mise à jour index.html
    if [ -f "$SCRIPT_DIR/src/index.html" ]; then
        cp "$SCRIPT_DIR/src/index.html" "/var/www/html/index.html"
        chown www-data:www-data /var/www/html/index.html 2>/dev/null || true
        chmod 644 /var/www/html/index.html 2>/dev/null || true
        print_success "index.html mis à jour"
    fi
    
    # Mise à jour du service systemd
    local service_updated=false
    if [ -f "$SCRIPT_DIR/config/pocsag.service" ]; then
        if ! cmp -s "$SCRIPT_DIR/config/pocsag.service" "/etc/systemd/system/pocsag.service" 2>/dev/null; then
            cp "$SCRIPT_DIR/config/pocsag.service" "/etc/systemd/system/"
            systemctl daemon-reload 2>/dev/null || true
            service_updated=true
            print_success "Service systemd mis à jour"
        fi
    fi
    
    # Mise à jour Nginx
    local nginx_updated=false
    if [ -f "$SCRIPT_DIR/config/nginx.conf" ]; then
        if ! cmp -s "$SCRIPT_DIR/config/nginx.conf" "/etc/nginx/sites-available/pocsag-monitor" 2>/dev/null; then
            cp "$SCRIPT_DIR/config/nginx.conf" "/etc/nginx/sites-available/pocsag-monitor"
            mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
            
            # Test de la configuration (robuste hors PATH)
            NGINX_BIN="$(nginx_bin)"
            if $NGINX_BIN -t 2>&1; then
                nginx_updated=true
                print_success "Configuration Nginx mise à jour"
            else
                print_error "Erreur dans la nouvelle configuration Nginx"
                $NGINX_BIN -t 2>&1 || true
                return 1
            fi
        fi
    fi
    
    # Mise à jour de la version
    if [ -f "$SCRIPT_DIR/VERSION" ]; then
        cp "$SCRIPT_DIR/VERSION" "/opt/pocsag/" 2>/dev/null || true
    else
        echo "$(date +%Y.%m.%d-%H%M)" > "/opt/pocsag/VERSION" 2>/dev/null || true
    fi
    
    # Redémarrage des services
    print_status "Redémarrage des services..."
    
    if [ "$nginx_updated" = true ]; then
        systemctl reload nginx
    fi
    
    systemctl start pocsag
    
    # Attendre que les services démarrent
    sleep 3
    
    # Vérification post-mise à jour
    if systemctl is-active --quiet pocsag; then
        print_success "Service POCSAG redémarré avec succès"
    else
        print_error "Erreur au redémarrage du service POCSAG"
        return 1
    fi
    
    if systemctl is-active --quiet nginx; then
        print_success "Nginx fonctionne correctement"
    else
        print_error "Erreur avec Nginx"
        return 1
    fi
}

# Rollback vers la dernière sauvegarde
rollback_to_backup() {
    print_warning "Restauration de la dernière sauvegarde..."
    
    if [ ! -L "$BACKUP_DIR/latest" ]; then
        print_error "Aucune sauvegarde trouvée !"
        exit 1
    fi
    
    local backup_path=$(readlink "$BACKUP_DIR/latest")
    
    if [ ! -d "$backup_path" ]; then
        print_error "Sauvegarde corrompue ou introuvable !"
        exit 1
    fi
    
    print_status "Restauration depuis : $backup_path"
    
    # Arrêt des services
    systemctl stop pocsag 2>/dev/null || true
    
    # Restauration des fichiers
    files_to_restore=(
        "/opt/pocsag/app.py"
        "/var/www/html/index.html"
        "/opt/pocsag/config.json"
        "/etc/systemd/system/pocsag.service"
        "/etc/nginx/sites-available/pocsag-monitor"
        "/var/www/html/data.json"
    )
    
    for file in "${files_to_restore[@]}"; do
        local backup_file="$backup_path$file"
        if [ -f "$backup_file" ]; then
            cp "$backup_file" "$file"
            print_status "Restauré: $file"
        fi
    done
    
    # Rechargement systemd et redémarrage
    systemctl daemon-reload 2>/dev/null || true
    NGINX_BIN="$(nginx_bin)"
    $NGINX_BIN -t 2>/dev/null && systemctl reload nginx 2>/dev/null || true
    systemctl start pocsag 2>/dev/null || true
    
    print_success "Rollback terminé avec succès !"
    
    # Affichage des informations de la sauvegarde restaurée
    if [ -f "$backup_path/backup_info.txt" ]; then
        echo -e "\n${BLUE}Informations de la sauvegarde restaurée :${NC}"
        cat "$backup_path/backup_info.txt"
    fi
}

# Test post-mise à jour
run_post_update_tests() {
    print_status "Tests post-mise à jour..."
    
    # Test API
    if curl -s http://localhost:8080/api/config > /dev/null; then
        print_success "✅ API Python accessible"
    else
        print_warning "⚠️  API Python non accessible"
    fi
    
    # Test interface web
    if curl -s http://localhost/ | grep -q "POCSAG Monitor"; then
        print_success "✅ Interface web accessible"
    else
        print_warning "⚠️  Interface web non accessible"
    fi
    
    # Test configuration
    if [ -f "/opt/pocsag/config.json" ] && python3 -m json.tool /opt/pocsag/config.json > /dev/null; then
        print_success "✅ Configuration JSON valide"
    else
        print_warning "⚠️  Problème avec la configuration"
    fi
}

# Affichage du résumé final
show_update_summary() {
    local version=$(get_current_version)
    local IP=$(hostname -I | awk '{print $1}')
    
    echo -e "\n${GREEN}╔═══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║         Mise à jour terminée !        ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
    
    echo -e "\n${BLUE}📋 Informations système :${NC}"
    echo -e "🔢 Version actuelle    : ${GREEN}$version${NC}"
    echo -e "🌐 Interface web      : ${GREEN}http://$IP${NC}"
    echo -e "📁 Sauvegarde créée   : ${GREEN}$BACKUP_DIR/latest${NC}"
    
    echo -e "\n${BLUE}🔧 Commandes utiles :${NC}"
    echo -e "📊 Vérifier le système : ${YELLOW}bash health-check.sh${NC}"
    echo -e "📝 Voir les logs       : ${YELLOW}sudo journalctl -u pocsag -f${NC}"
    echo -e "🔙 Rollback si problème: ${YELLOW}sudo bash update.sh --rollback${NC}"
    
    echo -e "\n${CYAN}💡 La configuration actuelle a été préservée${NC}"
}

# Liste des sauvegardes disponibles
list_backups() {
    echo -e "\n${BLUE}Sauvegardes disponibles :${NC}"
    
    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A $BACKUP_DIR 2>/dev/null)" ]; then
        print_warning "Aucune sauvegarde trouvée"
        return
    fi
    
    for backup in $(ls -1t "$BACKUP_DIR"/backup_* 2>/dev/null); do
        local backup_name=$(basename "$backup")
        local backup_date=$(echo $backup_name | sed 's/backup_//' | sed 's/_/ /')
        local size=$(du -sh "$backup" | cut -f1)
        
        if [ -L "$BACKUP_DIR/latest" ] && [ "$(readlink $BACKUP_DIR/latest)" = "$backup" ]; then
            echo -e "📦 ${GREEN}$backup_date${NC} (${size}) ${YELLOW}[DERNIÈRE]${NC}"
        else
            echo -e "📦 ${backup_date} (${size})"
        fi
        
        if [ -f "$backup/backup_info.txt" ]; then
            grep "Version:" "$backup/backup_info.txt" | sed 's/^/   /'
        fi
    done
}

# Fonction principale
main() {
    parse_args "$@"
    
    print_header
    
    # Mode rollback
    if [ "$ROLLBACK" = true ]; then
        check_root
        setup_backup_dir
        list_backups
        echo ""
        read -p "Confirmer la restauration de la dernière sauvegarde ? (oui/non) : " confirm
        if [ "$confirm" = "oui" ]; then
            rollback_to_backup
        else
            print_status "Rollback annulé"
        fi
        exit 0
    fi
    
    check_installation
    setup_backup_dir
    
    # Mise à jour du dépôt git EN PREMIER (pour que check_for_updates compare avec la dernière version distante)
    if [ -d "$SCRIPT_DIR/.git" ]; then
        print_status "Mise à jour du dépôt git (pull)..."
        git -C "$SCRIPT_DIR" fetch origin 2>&1 | tail -5 || true
        if ! git -C "$SCRIPT_DIR" pull --ff-only 2>&1 | tail -5; then
            print_warning "pull --ff-only echoue, reset hard sur origin/main..."
            if ! git -C "$SCRIPT_DIR" reset --hard origin/main 2>&1 | tail -5; then
                git -C "$SCRIPT_DIR" reset --hard origin/master 2>&1 | tail -5 || true
            fi
        fi
        print_status "Version depot: $(cat "$SCRIPT_DIR/VERSION" 2>/dev/null || echo '?')"
    fi

    # Vérification des mises à jour
    check_for_updates
    
    # Mode vérification seulement
    if [ "$CHECK_ONLY" = true ]; then
        if [ "$UPDATE_AVAILABLE" = true ]; then
            echo -e "\n${GREEN}✅ Des mises à jour sont disponibles${NC}"
            show_changes_summary
            echo -e "\n${BLUE}Pour mettre à jour : ${YELLOW}sudo bash update.sh${NC}"
        else
            echo -e "\n${GREEN}✅ Le système est à jour${NC}"
        fi
        exit 0
    fi
    
    # Mode sauvegarde seulement
    if [ "$BACKUP_ONLY" = true ]; then
        check_root
        create_backup
        print_success "Sauvegarde créée avec succès"
        list_backups
        exit 0
    fi
    
    # Pas de mises à jour disponibles
    if [ "$UPDATE_AVAILABLE" = false ] && [ "$FORCE_UPDATE" = false ]; then
        print_success "Le système est déjà à jour !"
        exit 0
    fi
    
    check_root
    
    # Affichage des changements
    if [ "$UPDATE_AVAILABLE" = true ]; then
        show_changes_summary
    fi
    
    # Confirmation si pas en mode force
    if [ "$FORCE_UPDATE" = false ]; then
        echo ""
        read -p "Procéder à la mise à jour ? (oui/non) : " confirm
        if [ "$confirm" != "oui" ]; then
            print_status "Mise à jour annulée"
            exit 0
        fi
    fi
    
    # Création de la sauvegarde
    create_backup
    
    # Mise à jour
    if update_files; then
        run_post_update_tests
        show_update_summary
    else
        print_error "Erreur lors de la mise à jour !"
        print_warning "Pour restaurer : sudo bash update.sh --rollback"
        exit 1
    fi
}

# Exécution
main "$@"