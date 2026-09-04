# POCSAG Monitor

Application autonome de décodage et supervision en temps réel des trames POCSAG (services d'urgence).

## Structure

```
v1/    → Version legacy (1.0.41) - app.py monolithe
v2/    → Version actuelle (2.0.0) - refonte modulaire
```

## Installation v2

```bash
git clone https://github.com/RouXx67/pocsag.git
cd pocsag
sudo bash v2/scripts/install.sh
```

Ouvrir `http://<ip>` — mot de passe par défaut : `admin`

## Architecture v2

```
RTL-SDR → rtl_fm → multimon-ng → Python (FastAPI) → Web UI + Discord + Telegram
                                    ↕
                                 SQLite
```

- **Backend** : FastAPI + SQLAlchemy async + SQLite
- **Auth** : JWT (bcrypt)
- **Frontend** : Vanilla JS, Leaflet, responsive
- **Tests** : pytest (29 tests)

## API

| Méthode | Route | Description |
|---------|-------|-------------|
| POST | /api/auth/login | Obtenir un token JWT |
| GET | /api/version | Version de l'app |
| GET | /api/config | Configuration complète |
| POST | /api/config | Mettre à jour la config |
| GET | /api/messages | Messages POCSAG (query: `search`, `urgent_only`) |
| GET | /api/stats | Statistiques du jour |
| POST | /api/clear-logs | Vider l'historique |
| GET/POST/DELETE | /api/aliases | CRUD alias RIC |
| GET/POST/DELETE | /api/blacklist | CRUD blacklist |
| GET | /api/service/status | Statut du service |
| POST | /api/service/restart | Redémarrer le service |
| GET | /api/logs | Logs journalctl |
| POST | /api/test-discord | Envoyer un test Discord |
| GET/POST | /api/update/check, /api/update/run | Mise à jour |

## v1 (legacy)

La version historique est dans `v1/`. Pour l'utiliser :

```bash
cd v1
sudo bash install.sh
```