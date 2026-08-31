#!/bin/bash
#
# POCSAG Monitor Pro - Installation rapide en une ligne
# Usage: curl -fsSL https://raw.githubusercontent.com/.../quick-install.sh | sudo bash
#

# Téléchargement et installation automatique
REPO_URL="https://github.com/RouXx67/pocsag"
TEMP_DIR="/tmp/pocsag-install"

echo "🚀 Installation rapide POCSAG Monitor Pro"

# Nettoyage du répertoire temporaire
rm -rf $TEMP_DIR
mkdir -p $TEMP_DIR
cd $TEMP_DIR

# Téléchargement du projet
echo "📥 Téléchargement des fichiers..."
if command -v git &> /dev/null; then
    git clone $REPO_URL .
else
    # Alternative avec wget/curl
    echo "Git non installé, téléchargement des fichiers individuels..."
    # Ici vous pourriez télécharger les fichiers un par un
fi

# Lancement de l'installation
echo "🔧 Lancement de l'installation..."
chmod +x setup.sh
./setup.sh

# Nettoyage
cd /
rm -rf $TEMP_DIR

echo "✅ Installation rapide terminée !"