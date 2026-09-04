# POCSAG Monitor (v1 - Legacy)

> ⚠️ **Cette version est archivée dans `v1/`.**  
> La refonte v2 est en cours dans le dossier `v2/`.

Application autonome de décodage et supervision en temps réel des trames POCSAG utilisées par les services d'urgence (Sapeurs-Pompiers, SAMU, etc.).

## Architecture Technique

### Composants principaux

1. **Récepteur SDR** : Clé USB RTL-SDR (rtl_fm)
   - VHF Bas : 85,955 MHz
   - VHF Haut : 173,5125 MHz
   - Décodage simultané des deux fréquences

2. **Décodeur** : multimon-ng
   - Support POCSAG 512, 1200 et 2400 bauds
   - Sortie texte parsée par regex

3. **Backend API** : Python 3 (app.py)
   - Serveur HTTP embarqué sur port 8080
   - Traitement des trames en temps réel
   - APIs de configuration

4. **Frontend Web** : HTML/CSS/JavaScript
   - Interface responsive dark mode
   - Statistiques en temps réel
   - Configuration via interface web

5. **Reverse Proxy** : Nginx (port 80)
   - Serveur web pour l'interface
   - Redirection API vers Python

## Fonctionnalités

### Notifications
- **Discord** : Webhook avec intégration cartes (Google Maps, OpenStreetMap)
- **Telegram** : Bot API avec géolocalisation automatique via BAN
- **Mots-clés prioritaires** : Mention @everyone sur alertes critiques

### Interface Web
- **Supervision temps réel** : Affichage des trames POCSAG
- **Statistiques** : Compteurs, RIC les plus actifs
- **Filtrage** : Recherche par RIC, alias, contenu
- **Géolocalisation** : Extraction d'adresse et liens Maps

### Configuration
- **Alias RIC** : Association RIC ↔ Nom d'engin
- **Blacklist** : Masquage des RIC de test
- **Paramètres** : Webhooks Discord/Telegram, mots-clés

## Installation Rapide ⚡

### Installation automatique (recommandée)
```bash
# Télécharger le projet
git clone https://github.com/RouXx67/pocsag.git
cd pocsag

# Installation complète en une commande
sudo bash setup.sh
```

### Installation manuelle
Si vous préférez l'installation étape par étape, consultez `INSTALLATION.md`

## Scripts Disponibles

### 🚀 Installation et Configuration
- **`setup.sh`** - Installation complète avec menu interactif
- **`setup-auto-update.sh`** - Configuration des mises à jour automatiques
- **`uninstall.sh`** - Désinstallation propre du système

### 🔄 Mise à Jour
- **`update.sh`** - Système de mise à jour intelligent avec sauvegarde
- **`auto-update.sh`** - Mises à jour automatiques (pour cron)
- **`deploy.sh`** - Déploiement rapide (legacy)

### 🔍 Maintenance et Diagnostic  
- **`health-check.sh`** - Diagnostic complet du système
- **`quick-install.sh`** - Installation en une ligne (à venir)

## API Endpoints

- `GET /api/config` : Récupération de la configuration
- `POST /api/config` : Sauvegarde de la configuration  
- `POST /api/clear-logs` : Vidage des logs
- `POST /api/test-discord` : Test des notifications

## Structure des données

### Trame POCSAG
```json
{
  "time": "14:30:15",
  "date": "31/08/2026", 
  "ric": "1234567",
  "alias": "VSAV ",
  "func": "1",
  "message": "SAP VERT A DOMICILE VSAV001.COND ******",
  "address": " ***** **** **** ******** "
}
```

### Configuration
```json
{
  "discord_webhook": "https://discord.com/api/webhooks/...",
  "telegram_bot_token": "123456:ABC-DEF...",
  "telegram_chat_id": "-100123456789",
  "notify_empty": true,
  "aliases": {
    "1234567": "VSAV Schirmeck"
  },
  "blacklist": ["9999999"],
  "keywords": ["AVP", "FEU", "DESINCARCERATION", "RENFORT", "URGENT"]
}
```

## Sécurité

- Interface accessible uniquement en réseau local
- Pas d'authentification (réseau interne sécurisé requis)
- Logs limités à 300 entrées (rotation automatique)
- Validation des entrées utilisateur côté client et serveur

## Dépannage

### Vérifier le service
```bash
sudo systemctl status pocsag
sudo journalctl -u pocsag -f
```

### Tester la réception
```bash
rtl_test -t  # Test du dongle RTL-SDR
rtl_fm -f 85955000 -s 22050 -g 42 | multimon-ng -t raw -a POCSAG1200 -
```

### Vérifier l'API
```bash
curl http://localhost:8080/api/config
```

## Licence

Usage personnel et éducatif uniquement. Respecter la législation locale concernant l'écoute des fréquences radio.
