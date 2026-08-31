#!/bin/bash
#
# POCSAG Monitor Pro - Mise à jour automatique (pour cron)
# Usage: bash auto-update.sh
#

# Configuration
LOG_FILE="/var/log/pocsag/auto-update.log"
NOTIFICATION_EMAIL=""  # Optionnel : email pour notifications
MAX_LOG_SIZE=10485760  # 10MB

# Fonction de log
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Rotation des logs si trop gros
rotate_log() {
    if [ -f "$LOG_FILE" ] && [ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE") -gt $MAX_LOG_SIZE ]; then
        mv "$LOG_FILE" "${LOG_FILE}.old"
        touch "$LOG_FILE"
        chmod 644 "$LOG_FILE"
    fi
}

# Notification par email (optionnel)
send_notification() {
    local subject="$1"
    local message="$2"
    
    if [ -n "$NOTIFICATION_EMAIL" ] && command -v mail &> /dev/null; then
        echo "$message" | mail -s "$subject" "$NOTIFICATION_EMAIL"
    fi
}

# Vérification de l'environnement
check_environment() {
    # Vérifier que nous sommes dans le bon répertoire
    if [ ! -f "update.sh" ]; then
        log_message "ERREUR: Script update.sh non trouvé dans $(pwd)"
        return 1
    fi
    
    # Vérifier les permissions root
    if [[ $EUID -ne 0 ]]; then
        log_message "ERREUR: Script doit être exécuté en root"
        return 1
    fi
    
    return 0
}

# Fonction principale
main() {
    # Création du répertoire de log
    mkdir -p "$(dirname "$LOG_FILE")"
    
    # Rotation des logs
    rotate_log
    
    log_message "=== Début de la vérification automatique ==="
    
    # Vérification de l'environnement
    if ! check_environment; then
        send_notification "POCSAG Auto-Update - ERREUR" "Erreur d'environnement lors de la vérification automatique"
        exit 1
    fi
    
    # Vérification des mises à jour disponibles
    log_message "Vérification des mises à jour..."
    
    # Exécution silencieuse de la vérification
    if bash update.sh --check-only > /dev/null 2>&1; then
        # Vérifier le code de retour pour savoir s'il y a des mises à jour
        if bash update.sh --check-only 2>&1 | grep -q "Mises à jour disponibles"; then
            log_message "Mises à jour détectées - Application automatique..."
            
            # Sauvegarde préventive
            if bash update.sh --backup-only >> "$LOG_FILE" 2>&1; then
                log_message "Sauvegarde préventive créée"
            else
                log_message "ERREUR: Échec de la sauvegarde préventive"
                send_notification "POCSAG Auto-Update - ERREUR" "Échec de la sauvegarde préventive"
                exit 1
            fi
            
            # Application de la mise à jour
            if bash update.sh --force >> "$LOG_FILE" 2>&1; then
                log_message "Mise à jour automatique réussie"
                send_notification "POCSAG Auto-Update - SUCCÈS" "Mise à jour automatique appliquée avec succès"
            else
                log_message "ERREUR: Échec de la mise à jour automatique"
                send_notification "POCSAG Auto-Update - ERREUR" "Échec de la mise à jour automatique - vérification manuelle requise"
                
                # Tentative de rollback automatique
                log_message "Tentative de rollback automatique..."
                if bash update.sh --rollback >> "$LOG_FILE" 2>&1; then
                    log_message "Rollback automatique réussi"
                    send_notification "POCSAG Auto-Update - ROLLBACK" "Rollback automatique effectué après échec de mise à jour"
                else
                    log_message "ERREUR CRITIQUE: Échec du rollback automatique"
                    send_notification "POCSAG Auto-Update - CRITIQUE" "ATTENTION: Échec du rollback automatique - intervention manuelle URGENTE requise"
                fi
            fi
        else
            log_message "Aucune mise à jour disponible"
        fi
    else
        log_message "ERREUR: Impossible de vérifier les mises à jour"
        send_notification "POCSAG Auto-Update - ERREUR" "Impossible de vérifier les mises à jour"
    fi
    
    # Vérification de santé post-update
    log_message "Vérification de santé du système..."
    if bash health-check.sh > /dev/null 2>&1; then
        log_message "Vérification de santé: OK"
    else
        log_message "ATTENTION: Problèmes détectés lors de la vérification de santé"
        send_notification "POCSAG Auto-Update - ATTENTION" "Problèmes détectés lors de la vérification de santé"
    fi
    
    log_message "=== Fin de la vérification automatique ==="
}

# Exécution avec gestion des erreurs
set -e
trap 'log_message "ERREUR: Script interrompu à la ligne $LINENO"' ERR

main "$@"