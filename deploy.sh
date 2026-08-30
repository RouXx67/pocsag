#!/bin/bash
# Script de déploiement rapide POCSAG Monitor Pro

echo "🔄 Déploiement POCSAG Monitor Pro"

# Arrêt du service si il tourne
echo "⏸️  Arrêt du service..."
systemctl stop pocsag 2>/dev/null || true

# Copie des fichiers mis à jour
echo "📁 Mise à jour des fichiers..."
cp src/app.py /opt/pocsag/app.py
cp src/index.html /var/www/html/

# Rechargement de la config systemd si modifiée
if [ -f "config/pocsag.service" ]; then
    echo "⚙️  Mise à jour du service systemd..."
    cp config/pocsag.service /etc/systemd/system/
    systemctl daemon-reload
fi

# Redémarrage des services
echo "🚀 Redémarrage des services..."
systemctl start pocsag
systemctl reload nginx

echo "✅ Déploiement terminé !"
echo "📊 Status : systemctl status pocsag"