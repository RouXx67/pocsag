#!/bin/bash
# Script de déploiement rapide POCSAG Monitor
# Ce script est maintenant un raccourci vers update.sh

echo "🔄 Déploiement rapide POCSAG Monitor"
echo "   (Utilise maintenant le système de mise à jour avancé)"

# Vérification que le script update.sh existe
if [ ! -f "update.sh" ]; then
    echo "❌ Script update.sh non trouvé !"
    echo "💡 Utilisation du mode legacy..."
    
    # Mode legacy (ancien comportement)
    echo "⏸️  Arrêt du service..."
    systemctl stop pocsag 2>/dev/null || true
    
    echo "📁 Mise à jour des fichiers..."
    cp src/app.py /opt/pocsag/app.py
    cp src/index.html /var/www/html/
    
    if [ -f "config/pocsag.service" ]; then
        echo "⚙️  Mise à jour du service systemd..."
        cp config/pocsag.service /etc/systemd/system/
        systemctl daemon-reload
    fi
    
    echo "🚀 Redémarrage des services..."
    systemctl start pocsag
    systemctl reload nginx
    
    echo "✅ Déploiement terminé !"
    echo "📊 Status : systemctl status pocsag"
else
    echo "🚀 Lancement de la mise à jour intelligente..."
    echo ""
    
    # Utiliser le nouveau système de mise à jour
    bash update.sh --force
fi