# Guide d'Installation POCSAG Monitor Pro

## 🚀 Installation Facile (Recommandée)

### Méthode 1 : Script automatique avec menu interactif
```bash
# Télécharger le projet
git clone https://github.com/votre-user/pocsag-monitor-pro.git
cd pocsag-monitor-pro

# Lancer l'installation interactive
sudo bash setup.sh
```

**Avantages :**
- ✅ Menu interactif avec choix
- ✅ Vérifications automatiques
- ✅ Détection de matériel RTL-SDR
- ✅ Configuration automatique
- ✅ Messages d'erreur détaillés

### Méthode 2 : Installation en une ligne (à venir)
```bash
curl -fsSL https://raw.githubusercontent.com/votre-user/pocsag-monitor-pro/main/quick-install.sh | sudo bash
```

## 🛠️ Scripts Disponibles

### `setup.sh` - Installation principale
```bash
sudo bash setup.sh
```
**Options du menu :**
1. **Installation complète** (recommandé)
2. **Installation sans démarrage** (pour configuration manuelle)
3. **Mise à jour uniquement** (si déjà installé)
4. **Vérification configuration** (diagnostic)
5. **Annuler**

**Ce que fait l'installation complète :**
- 🔍 Détection automatique de la distribution (Debian/Ubuntu/RedHat)
- 📦 Installation des dépendances (rtl-sdr, multimon-ng, nginx, python3)
- 🔧 Compilation de multimon-ng si nécessaire
- 📱 Test du matériel RTL-SDR
- 📁 Création des répertoires et permissions
- ⚙️ Configuration Nginx avec reverse proxy
- 🔄 Installation et activation du service systemd
- 🚀 Démarrage automatique des services

### `health-check.sh` - Diagnostic complet
```bash
bash health-check.sh
```
**Vérifications effectuées :**
- ✅ Statut des services (POCSAG + Nginx)
- ✅ Présence des fichiers critiques
- ✅ Dépendances installées
- ✅ Fonctionnement du RTL-SDR
- ✅ Connectivité réseau (API + Interface web)
- ✅ Logs d'erreurs récents
- ✅ Performance système (CPU, RAM, disque)

### `uninstall.sh` - Désinstallation complète
```bash
sudo bash uninstall.sh
```
**Options de désinstallation :**
- 🗑️ Suppression des services et fichiers
- 💾 Conservation optionnelle des logs
- 📦 Suppression optionnelle des dépendances

### `deploy.sh` - Mise à jour rapide
```bash
sudo bash deploy.sh
```
**Pour les développements :**
- 🔄 Arrêt temporaire du service
- 📁 Copie des nouveaux fichiers
- 🚀 Redémarrage automatique

## 📋 Prérequis Système

### Hardware
- **RTL-SDR USB dongle** (RTL2832U + R820T/R820T2)
- **Antenne VHF** (80-180 MHz) ou **discône large bande**
- **2 GB RAM minimum** (4 GB recommandé)
- **10 GB d'espace disque**

### Système d'exploitation
- **Ubuntu 18.04+** / **Debian 9+** (recommandé)
- **CentOS 7+** / **RHEL 7+**
- **Raspberry Pi OS** (Raspbian)

### Réseau
- **Accès Internet** pour les notifications Discord/Telegram
- **Port 80** libre pour l'interface web
- **Port 8080** libre pour l'API Python

## 🔧 Configuration Post-Installation

### 1. Configuration de base
```bash
# Éditer la configuration
sudo nano /opt/pocsag/config.json

# Redémarrer après modification
sudo systemctl restart pocsag
```

### 2. Configuration Discord
1. Créer un webhook Discord dans votre serveur
2. Copier l'URL du webhook
3. L'ajouter dans l'interface web (onglet Settings)

### 3. Configuration Telegram
1. Créer un bot avec @BotFather
2. Récupérer le token
3. Ajouter le bot à un groupe/canal
4. Récupérer l'ID du chat
5. Configurer dans l'interface web

### 4. Ajout des alias RIC
- Utiliser l'onglet "Alias RIC" dans l'interface web
- Associer les numéros RIC aux noms d'engins
- Exemple : `1234567` → `VSAV Schirmeck`

## 🚨 Dépannage

### Problème : Service POCSAG ne démarre pas
```bash
# Vérifier les logs
sudo journalctl -u pocsag -f

# Tester RTL-SDR manuellement
rtl_test -t

# Redémarrer le service
sudo systemctl restart pocsag
```

### Problème : Interface web inaccessible
```bash
# Vérifier Nginx
sudo systemctl status nginx

# Tester la configuration
sudo nginx -t

# Vérifier l'API Python
curl http://localhost:8080/api/config
```

### Problème : Pas de réception POCSAG
```bash
# Test manuel de réception
rtl_fm -f 85.955M -g 19.2 -s 22050 | multimon-ng -t raw -a POCSAG1200 -

# Vérifier l'antenne et les fréquences locales
# Ajuster le gain si nécessaire
```

## 📊 Surveillance

### Commandes utiles
```bash
# Statut des services
sudo systemctl status pocsag nginx

# Logs en temps réel
sudo journalctl -u pocsag -f

# Vérification complète
bash health-check.sh

# Statistiques système
htop
iotop
```

### Métriques importantes
- **CPU** : < 50% en utilisation normale
- **RAM** : < 1 GB pour l'application
- **Réseau** : Connectivité stable pour notifications
- **Messages/heure** : Varie selon l'activité locale

## 🔄 Maintenance

### Sauvegarde
```bash
# Sauvegarder la configuration
cp /opt/pocsag/config.json ~/backup/

# Sauvegarder les logs
cp /var/www/html/data.json ~/backup/
```

### Mise à jour
```bash
# Mise à jour système
sudo apt update && sudo apt upgrade

# Mise à jour de l'application
cd pocsag-monitor-pro
git pull
sudo bash deploy.sh
```

## 💡 Conseils d'Optimisation

### Performance
- **Gain RTL-SDR** : Commencer par 19.2 dB, ajuster selon l'environnement
- **Antenne** : Position élevée, loin des interférences
- **Système** : SSD recommandé pour les logs

### Sécurité
- **Firewall** : Limiter l'accès au port 80
- **VPN** : Accès distant via tunnel sécurisé
- **Logs** : Rotation automatique activée

### Fiabilité
- **Monitoring** : Utiliser `health-check.sh` en cron
- **Redémarrage automatique** : Service systemd configuré
- **Alertes** : Notifications en cas de problème