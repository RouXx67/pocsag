# POCSAG Monitor v2

Application autonome de décodage et supervision en temps réel des trames POCSAG (services d'urgence).

## Structure du projet

```
pocsag/
├── VERSION                  # Version actuelle (2.x.x)
├── README.md                # Ce fichier
├── v2/                      # Code source de la version 2
│   ├── backend/             # FastAPI + SQLite + services
│   ├── frontend/            # Interface web (HTML/CSS/JS)
│   ├── scripts/             # Installation/mise à jour (install.sh, update.sh)
│   ├── config/              # Exemples de config (service systemd, nginx)
│   └── requirements.txt     # Dépendances Python
│
└── .github/                 # Configuration GitHub (CI, issue templates)
```

> La version historique (v1) a été retirée du dépôt pour simplifier la maintenance. Seule la version v2 est maintenue.

## Installation (serveur Linux)

```bash
git clone https://github.com/RouXx67/pocsag.git
cd pocsag
sudo bash v2/scripts/install.sh
```

Ouvrir ensuite `http://<IP_DU_SERVEUR>` dans un navigateur.  
Mot de passe par défaut : **admin**

### Mise à jour

Le système intègre une mise à jour en un clic depuis l’interface web, ou manuellement via :

```bash
sudo bash /opt/pocsag/v2/scripts/update.sh
```

## Architecture

```
RTL‑SDR → rtl_fm → multimon‑ng → Python (FastAPI) → Web UI + Discord + Telegram
                                          ↕
                                       SQLite (messages, config, historique)
```

- **Backend** : FastAPI (ASGI) + SQLAlchemy async + SQLite (WAL activé)
- **Authentification** : JWT (bcrypt‑hashé)
- **Frontend** : Vanilla JS (ES6), Leaflet (carte), CSS3 responsive
- **Tests** : pytest (29 tests couvrant décodage, géocodage, API)
- **Historique** : journalisation complète des changements de paramètres

## Fonctionnalités principales

✅ Décodage temps réel (POCSAG 512 / 1200 / 2400) avec rtl_fm + multimon‑ng  
✅ Affichage live des trames dans une interface web moderne  
✅ Géocodage automatique (API Base Adresse Nationale) et affichage sur carte  
✅ Notifications Discord et Telegram (configurables)  
✅ Alias par RIC, blacklist, mots‑clés (urgences)  
✅ **Historique des paramètres** (depuis v2.7.0) avec restauration  
✅ Style cartographique par nature d’intervention (FEU/VSAV/AVP…) + fade temporel (24 h)  
✅ Mise à jour automatique (interface web ou script)  
✅ Service systemd + nginx (reverse proxy) intégré  

## API (v2)

| Méthode | Route | Description |
|---------|-------|-------------|
| POST | `/api/auth/login` | Obtenir un token JWT |
| GET | `/api/version` | Version de l’application |
| GET | `/api/config` | Configuration complète (radio, notifications, etc.) |
| POST | `/api/config` | Mettre à jour la config (historique automatique) |
| GET | `/api/config/history` | Historique des changements de paramètres |
| POST | `/api/config/history/{id}/restore` | Restaurer une valeur antérieure |
| GET | `/api/messages` | Messages POCSAG (filtres : `search`, `urgent_only`) |
| GET | `/api/stats` | Statistiques du jour (activité, heure par heure) |
| POST | `/api/clear-logs` | Vider l’historique des messages |
| CRUD | `/api/aliases` | Gestion des alias RIC (nom des engins) |
| CRUD | `/api/blacklist` | Gestion des RIC à ignorer |
| GET | `/api/service/status` | Statut du service (fréquence courante, actif) |
| POST | `/api/service/restart` | Redémarrer le service (soft) |
| GET | `/api/logs` | Logs systemd (journalctl) |
| GET | `/api/multimon‑logs` | Buffer live des logs rtl_fm/multimon‑ng |
| POST | `/api/test‑discord` | Envoyer un message de test vers Discord |
| GET/POST | `/api/update/check`, `/api/update/run` | Vérifier et lancer une mise à jour |

## Captures d’écran

*(À remplacer par des liens vers screenshots dans le futur)*

## Développement

### Prérequis
- Python 3.10+
- Node.js (pour éventuelles modifications frontend)
- RTL‑SDR (rtl_fm, multimon‑ng) installés

### Lancer en développement

```bash
cd v2/backend
python -m venv .venv
source .venv/bin/activate  # ou .venv\Scripts\activate sur Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

Le frontend est servi statiquement (fichiers dans `v2/frontend/`). Les modifications sont immédiates après rechargement.

## Licence

Projet sous licence MIT – voir le fichier [LICENSE](LICENSE) pour plus de détails.

## Remerciements

- **F4JTV** pour l’inspiration du décodage continu (intégré depuis v2.4.0)
- **OpenStreetMap** et **Leaflet** pour la cartographie
- **Base Adresse Nationale** pour le géocodage gratuit des adresses françaises