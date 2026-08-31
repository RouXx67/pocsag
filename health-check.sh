#!/bin/bash
#
# POCSAG Monitor - Vérification de santé du système
# Usage: bash health-check.sh
#

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[CHECK]${NC} $1"
}

print_ok() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════╗"
    echo "║        POCSAG Monitor             ║"
    echo "║      Vérification de santé            ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
}

check_services() {
    print_status "Vérification des services..."
    
    if systemctl is-active --quiet pocsag; then
        print_ok "Service POCSAG actif"
    else
        print_error "Service POCSAG inactif"
        echo "  → sudo systemctl start pocsag"
    fi
    
    if systemctl is-active --quiet nginx; then
        print_ok "Service Nginx actif"
    else
        print_error "Service Nginx inactif"
        echo "  → sudo systemctl start nginx"
    fi
}

check_files() {
    print_status "Vérification des fichiers..."
    
    files=(
        "/opt/pocsag/app.py:Application principale"
        "/var/www/html/index.html:Interface web"
        "/opt/pocsag/config.json:Configuration"
        "/etc/systemd/system/pocsag.service:Service systemd"
    )
    
    for file_info in "${files[@]}"; do
        file=$(echo $file_info | cut -d':' -f1)
        desc=$(echo $file_info | cut -d':' -f2)
        
        if [ -f "$file" ]; then
            print_ok "$desc présent"
        else
            print_error "$desc manquant : $file"
        fi
    done
}

check_dependencies() {
    print_status "Vérification des dépendances..."
    
    deps=(
        "rtl_test:RTL-SDR"
        "multimon-ng:Décodeur POCSAG"
        "python3:Python 3"
        "nginx:Serveur web"
    )
    
    for dep_info in "${deps[@]}"; do
        cmd=$(echo $dep_info | cut -d':' -f1)
        desc=$(echo $dep_info | cut -d':' -f2)
        
        if command -v $cmd &> /dev/null; then
            print_ok "$desc installé"
        else
            print_error "$desc manquant"
        fi
    done
}

check_rtl_sdr() {
    print_status "Vérification du matériel RTL-SDR..."
    
    if lsusb | grep -i "realtek\|rtl28" > /dev/null; then
        print_ok "Dongle RTL-SDR détecté"
        
        # Test rapide
        print_status "Test rapide du dongle..."
        if timeout 2s rtl_test -t &>/dev/null; then
            print_ok "Test RTL-SDR réussi"
        else
            print_warning "Test RTL-SDR échoué (peut être normal si utilisé)"
        fi
    else
        print_warning "Aucun dongle RTL-SDR détecté"
        echo "  → Vérifiez la connexion USB"
    fi
}

check_network() {
    print_status "Vérification réseau..."
    
    # Test de l'API locale
    if curl -s http://localhost:8080/api/config > /dev/null; then
        print_ok "API Python accessible"
    else
        print_error "API Python non accessible"
        echo "  → Vérifiez que le service POCSAG fonctionne"
    fi
    
    # Test de l'interface web
    if curl -s http://localhost/ | grep -q "POCSAG Monitor"; then
        print_ok "Interface web accessible"
    else
        print_error "Interface web non accessible"
        echo "  → Vérifiez la configuration Nginx"
    fi
    
    # Test de connectivité externe (pour les notifications)
    if curl -s --max-time 5 https://api.telegram.org > /dev/null; then
        print_ok "Connectivité Telegram OK"
    else
        print_warning "Problème de connectivité Telegram"
    fi
    
    if curl -s --max-time 5 https://discord.com > /dev/null; then
        print_ok "Connectivité Discord OK"
    else
        print_warning "Problème de connectivité Discord"
    fi
}

check_logs() {
    print_status "Vérification des logs..."
    
    # Logs système
    error_count=$(journalctl -u pocsag --since "1 hour ago" -p err --no-pager -q | wc -l)
    
    if [ $error_count -eq 0 ]; then
        print_ok "Aucune erreur dans les logs (1h)"
    else
        print_warning "$error_count erreurs dans les logs (1h)"
        echo "  → journalctl -u pocsag -p err"
    fi
    
    # Log des messages POCSAG
    if [ -f "/var/www/html/data.json" ]; then
        msg_count=$(cat /var/www/html/data.json | jq length 2>/dev/null || echo "?")
        print_ok "$msg_count messages POCSAG enregistrés"
    else
        print_warning "Pas de fichier de données POCSAG"
    fi
}

check_performance() {
    print_status "Vérification des performances..."
    
    # Utilisation CPU (sans bc, fallback awk)
    cpu_usage=$(top -bn1 2>/dev/null | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    cpu_usage=${cpu_usage:-0}
    # Comparaison sans bc : awk gère les floats
    if awk "BEGIN {exit !($cpu_usage < 80)}"; then
        print_ok "Utilisation CPU acceptable ($cpu_usage%)"
    else
        print_warning "Utilisation CPU élevée ($cpu_usage%)"
    fi
    
    # Utilisation mémoire
    mem_usage=$(free 2>/dev/null | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    mem_usage=${mem_usage:-0}
    if awk "BEGIN {exit !($mem_usage < 80)}"; then
        print_ok "Utilisation mémoire acceptable ($mem_usage%)"
    else
        print_warning "Utilisation mémoire élevée ($mem_usage%)"
    fi
    
    # Espace disque
    disk_usage=$(df / | awk 'NR==2 {print $5}' | cut -d'%' -f1)
    if [ $disk_usage -lt 80 ]; then
        print_ok "Espace disque suffisant ($disk_usage%)"
    else
        print_warning "Espace disque faible ($disk_usage%)"
    fi
}

show_summary() {
    echo -e "\n${BLUE}📊 Résumé de santé :${NC}"
    echo -e "🕐 Vérification effectuée le : $(date)"
    echo -e "💻 Système : $(uname -a)"
    
    local IP=$(hostname -I | awk '{print $1}')
    echo -e "🌐 Interface web : http://$IP"
    
    echo -e "\n${BLUE}🔧 Commandes utiles :${NC}"
    echo "📊 Statut services  : sudo systemctl status pocsag nginx"
    echo "📝 Logs temps réel  : sudo journalctl -u pocsag -f"
    echo "🔄 Redémarrage      : sudo systemctl restart pocsag"
    echo "⚙️  Configuration    : sudo nano /opt/pocsag/config.json"
}

# Fonction principale
main() {
    print_header
    
    check_services
    echo ""
    check_files
    echo ""
    check_dependencies
    echo ""
    check_rtl_sdr
    echo ""
    check_network
    echo ""
    check_logs
    echo ""
    check_performance
    
    show_summary
}

# Exécution
main