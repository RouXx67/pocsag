#!/bin/bash
#
# POCSAG Monitor Pro - Script d'installation automatique
# Usage: sudo bash setup.sh
#

set -e  # Arrêt sur erreur

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonction d'affichage
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
    echo "║        POCSAG Monitor Pro             ║"
    echo "║     Installation automatique          ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
}

# Vérification des privilèges root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "Ce script doit être exécuté en root (sudo)"
        echo "Usage: sudo bash setup.sh"
        exit 1
    fi
}

# Vérification de la distribution
check_distro() {
    if [ -f /etc/debian_version ]; then
        DISTRO="debian"
        print_status "Distribution Debian/Ubuntu détectée"
    elif [ -f /etc/redhat-release ]; then
        DISTRO="redhat"
        print_status "Distribution RedHat/CentOS détectée"
    else
        print_warning "Distribution non reconnue, on continue avec apt..."
        DISTRO="debian"
    fi
}

# Installation des dépendances
install_dependencies() {
    print_status "Mise à jour des paquets..."
    
    if [ "$DISTRO" = "debian" ]; then
        apt update
        print_status "Installation des dépendances système..."
        apt install -y rtl-sdr multimon-ng python3 python3-pip nginx curl wget git
        
        # Vérification spéciale pour multimon-ng (parfois pas dans les dépôts)
        if ! command -v multimon-ng &> /dev/null; then
            print_warning "multimon-ng non trouvé, compilation depuis les sources..."
            apt install -y build-essential cmake libpulse-dev
            cd /tmp
            git clone https://github.com/EliasOenal/multimon-ng.git
            cd multimon-ng
            mkdir build && cd build
            cmake ..
            make
            make install
            cd /
        fi
        
    elif [ "$DISTRO" = "redhat" ]; then
        yum update -y
        yum install -y rtl-sdr python3 python3-pip nginx curl wget git gcc cmake make
        print_warning "multimon-ng doit être compilé manuellement sur RedHat"
    fi
    
    print_status "Installation des dépendances Python..."
    # Debian 13 / Python 3.13 : environnement externement géré -> preferer apt, fallback pip --break-system-packages
    if ! apt install -y python3-requests 2>/dev/null; then
        pip3 install --break-system-packages requests 2>/dev/null || pip3 install requests 2>/dev/null || true
    fi
    # Vérification
    if ! python3 -c "import requests" 2>/dev/null; then
        print_warning "Module requests non disponible - notifications Telegram/Discord limitees"
    fi
}

# Vérification du matériel RTL-SDR
check_rtl_sdr() {
    print_status "Vérification du dongle RTL-SDR..."
    
    if lsusb | grep -i "realtek\|rtl28"; then
        print_success "Dongle RTL-SDR détecté !"
    else
        print_warning "Aucun dongle RTL-SDR détecté"
        print_warning "Assurez-vous qu'il est bien connecté"
    fi
    
    # Test rapide
    print_status "Test rapide du RTL-SDR..."
    timeout 3s rtl_test -t || print_warning "Test RTL-SDR échoué (normal si pas de dongle)"
}

# Création des répertoires
create_directories() {
    print_status "Création des répertoires..."
    
    mkdir -p /opt/pocsag
    mkdir -p /var/www/html
    mkdir -p /var/log/pocsag
    
    # Permissions
    chown -R www-data:www-data /var/www/html
    chmod 755 /opt/pocsag
    chmod 755 /var/log/pocsag
}

# Copie des fichiers
copy_files() {
    print_status "Installation des fichiers..."
    
    # Vérification que les fichiers source existent
    if [ ! -f "src/app.py" ]; then
        print_error "Fichier src/app.py manquant !"
        exit 1
    fi
    
    if [ ! -f "src/index.html" ]; then
        print_error "Fichier src/index.html manquant !"
        exit 1
    fi
    
    # Copie des fichiers
    cp src/app.py /opt/pocsag/app.py
    cp src/index.html /var/www/html/index.html
    
    # Configuration par défaut
    if [ -f "config/config.json.example" ]; then
        cp config/config.json.example /opt/pocsag/
        if [ ! -f "/opt/pocsag/config.json" ]; then
            cp config/config.json.example /opt/pocsag/config.json
            print_status "Fichier de configuration créé: /opt/pocsag/config.json"
        fi
    fi
    
    # Permissions
    chown root:root /opt/pocsag/app.py
    chmod 644 /opt/pocsag/app.py
    chmod 644 /opt/pocsag/config.json
}

# Configuration Nginx
configure_nginx() {
    print_status "Configuration de Nginx..."
    
    if [ -f "config/nginx.conf" ]; then
        cp config/nginx.conf /etc/nginx/sites-available/pocsag-monitor
        
        # Activation du site
        ln -sf /etc/nginx/sites-available/pocsag-monitor /etc/nginx/sites-enabled/
        
        # Désactivation du site par défaut
        if [ -L "/etc/nginx/sites-enabled/default" ]; then
            rm /etc/nginx/sites-enabled/default
        fi
        
        # Test de la configuration
        if nginx -t; then
            print_success "Configuration Nginx valide"
        else
            print_error "Erreur dans la configuration Nginx"
            exit 1
        fi
    else
        print_error "Fichier config/nginx.conf manquant !"
        exit 1
    fi
}

# Configuration du service systemd
configure_service() {
    print_status "Configuration du service systemd..."
    
    if [ -f "config/pocsag.service" ]; then
        cp config/pocsag.service /etc/systemd/system/
        
        # Rechargement systemd
        systemctl daemon-reload
        
        print_success "Service pocsag installé"
    else
        print_error "Fichier config/pocsag.service manquant !"
        exit 1
    fi
}

# Démarrage des services
start_services() {
    print_status "Démarrage des services..."
    
    # Activation automatique au boot
    systemctl enable nginx
    systemctl enable pocsag
    
    # Démarrage
    systemctl restart nginx
    
    # Attendre un peu avant de démarrer pocsag
    sleep 2
    systemctl start pocsag
    
    # Vérification du statut
    sleep 3
    if systemctl is-active --quiet nginx; then
        print_success "Nginx démarré"
    else
        print_error "Erreur démarrage Nginx"
    fi
    
    if systemctl is-active --quiet pocsag; then
        print_success "Service POCSAG démarré"
    else
        print_warning "Service POCSAG non démarré (normal si pas de RTL-SDR)"
    fi
}

# Affichage des informations finales
show_info() {
    local IP=$(hostname -I | awk '{print $1}')
    
    echo -e "\n${GREEN}╔═══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           Installation terminée !      ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
    
    echo -e "\n${BLUE}📋 Informations d'accès :${NC}"
    echo -e "🌐 Interface web : ${GREEN}http://$IP${NC}"
    echo -e "📁 Configuration : ${GREEN}/opt/pocsag/config.json${NC}"
    
    echo -e "\n${BLUE}🔧 Commandes utiles :${NC}"
    echo -e "📊 Status services   : ${YELLOW}systemctl status pocsag nginx${NC}"
    echo -e "📝 Logs temps réel   : ${YELLOW}journalctl -u pocsag -f${NC}"
    echo -e "🔄 Redémarrer POCSAG : ${YELLOW}systemctl restart pocsag${NC}"
    echo -e "⚙️  Éditer config     : ${YELLOW}nano /opt/pocsag/config.json${NC}"
    
    echo -e "\n${BLUE}⚠️  Étapes suivantes :${NC}"
    echo "1. Configurer Discord/Telegram dans l'interface web"
    echo "2. Ajouter vos alias RIC dans l'onglet 'Alias RIC'"
    echo "3. Tester la réception avec : rtl_test -t"
    echo "4. Vérifier les logs : journalctl -u pocsag -f"
    
    echo -e "\n${YELLOW}💡 Pour désinstaller : sudo bash uninstall.sh${NC}"
}

# Menu interactif
interactive_menu() {
    echo -e "\n${BLUE}Que souhaitez-vous faire ?${NC}"
    echo "1) Installation complète (recommandé)"
    echo "2) Installation sans démarrage des services"
    echo "3) Mise à jour uniquement"
    echo "4) Vérification de la configuration"
    echo "5) Annuler"
    
    read -p "Votre choix [1-5] : " choice
    
    case $choice in
        1)
            return 0  # Installation complète
            ;;
        2)
            SKIP_START=true
            return 0
            ;;
        3)
            UPDATE_ONLY=true
            return 0
            ;;
        4)
            check_installation
            exit 0
            ;;
        5)
            print_status "Installation annulée"
            exit 0
            ;;
        *)
            print_error "Choix invalide"
            interactive_menu
            ;;
    esac
}

# Vérification de l'installation existante
check_installation() {
    print_status "Vérification de l'installation..."
    
    echo -e "\n${BLUE}Services :${NC}"
    systemctl is-active --quiet nginx && echo -e "✅ Nginx : ${GREEN}actif${NC}" || echo -e "❌ Nginx : ${RED}inactif${NC}"
    systemctl is-active --quiet pocsag && echo -e "✅ POCSAG : ${GREEN}actif${NC}" || echo -e "❌ POCSAG : ${RED}inactif${NC}"
    
    echo -e "\n${BLUE}Fichiers :${NC}"
    [ -f "/opt/pocsag/app.py" ] && echo -e "✅ app.py : ${GREEN}présent${NC}" || echo -e "❌ app.py : ${RED}manquant${NC}"
    [ -f "/var/www/html/index.html" ] && echo -e "✅ index.html : ${GREEN}présent${NC}" || echo -e "❌ index.html : ${RED}manquant${NC}"
    [ -f "/opt/pocsag/config.json" ] && echo -e "✅ config.json : ${GREEN}présent${NC}" || echo -e "❌ config.json : ${RED}manquant${NC}"
    
    echo -e "\n${BLUE}RTL-SDR :${NC}"
    if command -v rtl_test &> /dev/null; then
        echo -e "✅ rtl-sdr : ${GREEN}installé${NC}"
    else
        echo -e "❌ rtl-sdr : ${RED}manquant${NC}"
    fi
    
    if command -v multimon-ng &> /dev/null; then
        echo -e "✅ multimon-ng : ${GREEN}installé${NC}"
    else
        echo -e "❌ multimon-ng : ${RED}manquant${NC}"
    fi
}

# Fonction principale
main() {
    print_header
    check_root
    
    # Menu interactif si pas d'arguments
    if [ $# -eq 0 ]; then
        interactive_menu
    fi
    
    # Installation mise à jour seulement
    if [ "$UPDATE_ONLY" = true ]; then
        print_status "Mode mise à jour"
        copy_files
        systemctl restart pocsag nginx
        print_success "Mise à jour terminée"
        exit 0
    fi
    
    # Installation complète
    check_distro
    install_dependencies
    check_rtl_sdr
    create_directories
    copy_files
    configure_nginx
    configure_service
    
    if [ "$SKIP_START" != true ]; then
        start_services
    fi
    
    show_info
}

# Variables globales
SKIP_START=false
UPDATE_ONLY=false

# Exécution
main "$@"