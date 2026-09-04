# Guide de Mise à Jour - POCSAG Monitor

## 🚀 Système de Mise à Jour Intelligent

POCSAG Monitor dispose d'un système de mise à jour avancé avec sauvegarde automatique et rollback.

## 📋 Scripts de Mise à Jour

### `update.sh` - Script principal de mise à jour

#### Utilisation basique
```bash
# Vérifier s'il y a des mises à jour
bash update.sh --check-only

# Mise à jour interactive (recommandé)
sudo bash update.sh

# Mise à jour forcée sans confirmation  
sudo bash update.sh --force
```

#### Options avancées
```bash
# Faire seulement une sauvegarde
sudo bash update.sh --backup-only

# Restaurer la dernière sauvegarde
sudo bash update.sh --rollback

# Aide complète
bash update.sh --help
```

### `auto-update.sh` - Mises à jour automatiques

Script conçu pour fonctionner avec cron, avec logging et notifications.

```bash
# Test manuel
sudo bash auto-update.sh

# Configuration automatique
sudo bash setup-auto-update.sh
```

### `deploy.sh` - Déploiement rapide (legacy)

Maintenant un raccourci vers le système de mise à jour avancé.

```bash
sudo bash deploy.sh
```

## 🔍 Fonctionnalités Avancées

### 1. Détection Automatique des Changements

Le script analyse automatiquement :
- ✅ Modifications dans `src/app.py`
- ✅ Modifications dans `src/index.html` 
- ✅ Changements de configuration systemd
- ✅ Mises à jour Nginx
- ✅ Nouveaux commits Git (si disponible)

### 2. Système de Sauvegarde Intelligent

```bash
# Sauvegardes automatiques dans /opt/pocsag/backups/
backup_20240831_143022/
├── opt/pocsag/app.py           # Backup du backend
├── var/www/html/index.html     # Backup de l'interface
├── opt/pocsag/config.json      # Backup de la config
├── etc/systemd/system/pocsag.service
└── backup_info.txt             # Métadonnées
```

**Conservation :** Les 5 dernières sauvegardes sont conservées automatiquement.

### 3. Rollback Sécurisé

En cas de problème après mise à jour :
```bash
# Rollback automatique
sudo bash update.sh --rollback

# Liste des sauvegardes disponibles
sudo bash update.sh --check-only
```

### 4. Tests Post-Mise à Jour

Après chaque mise à jour, vérification automatique :
- ✅ API Python accessible (port 8080)
- ✅ Interface web fonctionnelle (port 80)
- ✅ Configuration JSON valide
- ✅ Services systemd actifs

## 🤖 Mises à Jour Automatiques

### Configuration Simple

```bash
sudo bash setup-auto-update.sh
```

**Menu interactif :**
1. **Quotidien à 03:00** (recommandé)
2. **Hebdomadaire dimanche 02:00**
3. **Planification personnalisée**
4. **Désactiver**
5. **Voir la configuration actuelle**

### Exemple de Configuration Cron

```bash
# Mise à jour quotidienne à 03:00
0 3 * * * cd /path/to/pocsag && bash auto-update.sh

# Mise à jour hebdomadaire le dimanche à 02:00
0 2 * * 0 cd /path/to/pocsag && bash auto-update.sh
```

### Notifications Email (Optionnel)

Configuration automatique avec `mailutils` :
- ✅ Notification en cas de succès
- ✅ Alerte en cas d'erreur
- ✅ Notification de rollback automatique

## 📊 Monitoring et Logs

### Logs des Mises à Jour Automatiques

```bash
# Voir les logs en temps réel
tail -f /var/log/pocsag/auto-update.log

# Dernières mises à jour
grep "Mise à jour" /var/log/pocsag/auto-update.log

# Erreurs uniquement
grep "ERREUR" /var/log/pocsag/auto-update.log
```

### Vérification de Santé Post-Update

```bash
# Diagnostic complet
bash health-check.sh

# Status des services
systemctl status pocsag nginx

# Logs système
journalctl -u pocsag -f
```

## 🛠️ Exemples d'Utilisation

### Mise à Jour de Développement

```bash
# 1. Modification du code source
nano src/app.py

# 2. Vérification des changements
bash update.sh --check-only

# 3. Application avec sauvegarde automatique
sudo bash update.sh
```

### Mise à Jour en Production

```bash
# 1. Sauvegarde préventive
sudo bash update.sh --backup-only

# 2. Téléchargement des nouveautés
git pull origin main

# 3. Application silencieuse
sudo bash update.sh --force

# 4. Vérification post-update
bash health-check.sh
```

### Gestion d'Incident

```bash
# En cas de problème après mise à jour
sudo bash update.sh --rollback

# Vérification que tout fonctionne
systemctl status pocsag
curl http://localhost/

# Si problème persiste, restauration manuelle
ls -la /opt/pocsag/backups/
```

## 🔧 Configuration Avancée

### Variables d'Environnement

Dans `auto-update.sh` :
```bash
# Taille maximale des logs (10MB par défaut)
MAX_LOG_SIZE=10485760

# Email pour notifications (vide par défaut)
NOTIFICATION_EMAIL="admin@example.com"
```

### Personnalisation des Sauvegardes

Modifier les chemins dans `update.sh` :
```bash
BACKUP_DIR="/opt/pocsag/backups"     # Répertoire des sauvegardes
```

### Exclusions de Mise à Jour

Pour exclure certains fichiers de la mise à jour, modifier la fonction `update_files()` dans `update.sh`.

## 🚨 Résolution de Problèmes

### Problème : Mise à jour échoue

```bash
# 1. Vérifier les logs
journalctl -u pocsag -n 50

# 2. Vérifier les permissions
ls -la /opt/pocsag/
ls -la /var/www/html/

# 3. Test des services
systemctl status pocsag nginx

# 4. Rollback si nécessaire
sudo bash update.sh --rollback
```

### Problème : Sauvegarde corrompue

```bash
# Lister les sauvegardes
ls -la /opt/pocsag/backups/

# Vérifier le contenu
cat /opt/pocsag/backups/latest/backup_info.txt

# Restauration manuelle si nécessaire
sudo cp /opt/pocsag/backups/backup_YYYYMMDD_HHMMSS/opt/pocsag/app.py /opt/pocsag/
sudo systemctl restart pocsag
```

### Problème : Cron ne fonctionne pas

```bash
# Vérifier que cron est actif
systemctl status cron

# Vérifier la syntaxe du crontab
crontab -l

# Logs de cron
grep CRON /var/log/syslog | tail -10

# Test manuel
sudo bash auto-update.sh
```

## 📈 Bonnes Pratiques

### 1. Planification des Mises à Jour
- **Production** : Mise à jour hebdomadaire en période de faible activité
- **Développement** : Mise à jour quotidienne
- **Test préalable** : Toujours tester sur un environnement de développement

### 2. Surveillance
- **Logs réguliers** : Vérifier `/var/log/pocsag/auto-update.log` hebdomadairement
- **Health checks** : Exécuter `health-check.sh` après chaque mise à jour
- **Notifications** : Configurer les emails pour les mises à jour critiques

### 3. Sauvegardes
- **Fréquence** : Sauvegarde automatique avant chaque mise à jour
- **Conservation** : Garder au minimum 5 sauvegardes
- **Vérification** : Tester périodiquement la procédure de rollback

### 4. Sécurité
- **Permissions** : Vérifier régulièrement les permissions des fichiers
- **Accès** : Limiter l'accès aux scripts de mise à jour
- **Audit** : Conserver les logs de mise à jour pour audit

## 🔗 Liens Utiles

- **Installation** : `INSTALLATION.md`
- **Diagnostic** : `health-check.sh`  
- **Configuration** : `/opt/pocsag/config.json`
- **Logs système** : `journalctl -u pocsag -f`
- **Logs auto-update** : `/var/log/pocsag/auto-update.log`