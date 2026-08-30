# Structure POCSAG Monitor Pro

## Arborescence corrigée ✅

```
pocsag/
├── src/
│   ├── app.py                   # Backend Python (décodage + API)
│   └── index.html               # Interface web (frontend)
│
├── config/
│   ├── pocsag.service           # Service systemd principal
│   ├── config.json.example      # Configuration exemple
│   ├── nginx.conf               # Configuration reverse proxy
│   └── pocsag-monitor.service   # Service systemd alternatif
│
├── install.sh                   # Script d'installation complète
├── deploy.sh                    # Script de déploiement rapide
├── README.md                    # Documentation principale
├── NOTES_TECHNIQUES.md          # Documentation technique RTL-SDR
└── STRUCTURE.md                 # Ce fichier
```

## Déploiement

### Installation initiale
```bash
sudo bash install.sh
```

### Mise à jour après modifications
```bash
sudo bash deploy.sh
```

## Fichiers de production

| Source | Destination | Description |
|--------|-------------|-------------|
| `src/app.py` | `/opt/pocsag/app.py` | Backend Python |
| `src/index.html` | `/var/www/html/index.html` | Interface web |
| `config/pocsag.service` | `/etc/systemd/system/pocsag.service` | Service systemd |
| `config/nginx.conf` | `/etc/nginx/sites-available/pocsag-monitor` | Config Nginx |
| `config/config.json.example` | `/opt/pocsag/config.json.example` | Config exemple |

## Services actifs

- **pocsag.service** : Décodage RTL-SDR → multimon-ng → Python
- **nginx.service** : Serveur web + reverse proxy API