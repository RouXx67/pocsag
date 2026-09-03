import sys
import re
import json
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

CONFIG_FILE = "/opt/pocsag/config.json"
LOG_FILE = "/var/www/html/data.json"
SERVICE_FILE = "/etc/systemd/system/pocsag.service"
VERSION_FILE = "/opt/pocsag/VERSION"
DEFAULT_FREQUENCIES = ["85.955M", "173512.5k"]

def get_version():
    try:
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    except Exception:
        try:
            with open("VERSION", "r") as f:
                return f.read().strip()
        except Exception:
            return "1.0.0"

def parse_service_file():
    """Parse le fichier service et retourne les paramètres structurés + brut."""
    result = {
        "description": "Decoder POCSAG RTL-SDR vers Web, Telegram et Discord",
        "after": "network.target nginx.service",
        "service_type": "simple",
        "user": "root",
        "squelch": 50,
        "gain": "19.2",
        "sample_rate": "176400",
        "output_rate": "22050",
        "restart": "always",
        "restart_sec": 5,
        "raw": ""
    }
    try:
        with open(SERVICE_FILE, "r") as f:
            content = f.read()
        result["raw"] = content
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("Description="):
                result["description"] = line.split("=", 1)[1]
            elif line.startswith("After="):
                result["after"] = line.split("=", 1)[1]
            elif line.startswith("Type="):
                result["service_type"] = line.split("=", 1)[1]
            elif line.startswith("User="):
                result["user"] = line.split("=", 1)[1]
            elif line.startswith("Restart="):
                result["restart"] = line.split("=", 1)[1]
            elif line.startswith("RestartSec="):
                try: result["restart_sec"] = int(line.split("=", 1)[1])
                except ValueError: pass
            elif line.startswith("ExecStart="):
                exec_start = line.split("=", 1)[1]
                m = re.search(r'rtl_fm\s+(.*?)\s*\|', exec_start)
                if m:
                    rtl_args = m.group(1)
                    sl = re.search(r'-l\s+(\S+)', rtl_args)
                    if sl:
                        try: result["squelch"] = int(sl.group(1))
                        except ValueError: pass
                    g = re.search(r'-g\s+(\S+)', rtl_args)
                    if g: result["gain"] = g.group(1)
                    s = re.search(r'-s\s+(\S+)', rtl_args)
                    if s: result["sample_rate"] = s.group(1)
                    rm = re.search(r'-r\s+(\S+)', rtl_args)
                    if rm: result["output_rate"] = rm.group(1)
    except Exception:
        pass
    return result

DEFAULT_CONFIG = {
    "discord_webhook": "",
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "notify_empty": True,
    "aliases": {},
    "blacklist": [],
    "keywords": ["AVP", "FEU", "DESINCARCERATION", "RENFORT", "URGENT"],
    "frequencies": DEFAULT_FREQUENCIES.copy(),
    "admin_password": "admin"
}

def get_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
            # Migration : ajouter frequencies si absent
            if "frequencies" not in cfg:
                cfg["frequencies"] = DEFAULT_FREQUENCIES.copy()
            return cfg
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(cfg):
    # Préserver le bloc service existant si absent de la requête client
    if "service" not in cfg:
        old_cfg = get_config()
        if "service" in old_cfg:
            cfg["service"] = old_cfg["service"]

    # Normaliser frequencies avant sauvegarde
    if "frequencies" in cfg:
        cfg["frequencies"] = normalize_frequencies(cfg["frequencies"])
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    # Mettre à jour le service systemd (fréquences ET paramètres RTL-SDR)
    try:
        freqs = cfg.get("frequencies", DEFAULT_FREQUENCIES)
        update_pocsag_service(freqs)
    except Exception as e:
        print(f"Erreur update service: {e}")

FREQ_RE = re.compile(r"^\s*\d+(\.\d+)?\s*[kKmM]?(?:Hz)?\s*$")

def normalize_frequencies(freqs):
    """Valide et normalise la liste de fréquences : max 3, format rtl_fm."""
    if not isinstance(freqs, list):
        return DEFAULT_FREQUENCIES.copy()
    cleaned = []
    for f in freqs:
        if not isinstance(f, str):
            f = str(f)
        f = f.strip()
        if not f:
            continue
        # Accepte 85.955M, 85.955MHz, 173512.5k, 173.5125M ...
        # Normaliser : supprimer espaces, garder tel quel si match
        if FREQ_RE.match(f):
            # Supprimer espaces internes et uniformiser : ex "85.955 MHz" -> "85.955M"
            f = re.sub(r"\s+", "", f)
            cleaned.append(f)
        if len(cleaned) >= 3:
            break
    return cleaned if cleaned else DEFAULT_FREQUENCIES.copy()

def update_pocsag_service(frequencies):
    """Réécrit ExecStart dans /etc/systemd/system/pocsag.service avec les fréquences données."""
    freqs = normalize_frequencies(frequencies)
    cfg = get_config()
    svc = cfg.get("service", {})
    squelch = svc.get("squelch", 50)
    gain = svc.get("gain", "19.2")
    sample_rate = svc.get("sample_rate", "176400")
    output_rate = svc.get("output_rate", "22050")
    restart = svc.get("restart", "always")
    restart_sec = svc.get("restart_sec", 5)
    freq_args = " ".join(f"-f {f}" for f in freqs)
    exec_start = f'/bin/bash -c "rtl_fm {freq_args} -M fm -s {sample_rate} -r {output_rate} -E offset -l {squelch} -g {gain} | multimon-ng -t raw -a POCSAG512 -a POCSAG1200 -a POCSAG2400 -f alpha - | python3 /opt/pocsag/app.py"'
    # Template exact demandé par l'utilisateur (sans toucher autre que ExecStart)
    description = svc.get("description", "Decoder POCSAG RTL-SDR vers Web, Telegram et Discord")
    after = svc.get("after", "network.target nginx.service")
    service_type = svc.get("service_type", "simple")
    user = svc.get("user", "root")
    content = f"""[Unit]
Description={description}
After={after}

[Service]
Type={service_type}
User={user}
ExecStart={exec_start}
Restart={restart}
RestartSec={restart_sec}

[Install]
WantedBy=multi-user.target
"""
    # Éviter réécriture inutile
    try:
        with open(SERVICE_FILE, "r") as f:
            existing = f.read()
        if existing == content:
            return True
    except Exception:
        pass
    with open(SERVICE_FILE, "w") as f:
        f.write(content)
    # Rechargement systemd (non bloquant)
    try:
        import subprocess
        subprocess.run(["systemctl", "daemon-reload"], timeout=5)
    except Exception as e:
        print(f"daemon-reload echoue: {e}")
    return True

def extract_address(message):
    if not message:
        return ""
    
    cleaned = message
    # Supprimer les préfixes d'intervention courants
    for prefix in ["AVP", "SAP", "FEU", "SECOURS", "INTERVENTION", "VL CONTRE ARBRE", "PL CONTRE ARBRE", "DEGAGEMENT", "RECONNAISSANCE"]:
        if cleaned.upper().startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()

    # Supprimer l'engin et son rôle (ex: VSAV001.COND ou FPT001)
    cleaned = re.sub(r'\b[A-Z]{3,}\d{3}(?:\.[A-Z0-9]+)?\s*', '', cleaned)
    cleaned = cleaned.strip()

    # Normalisation si la ville est en premier suivie de la rue (ex: THANN 12 AVENUE DE LA REPUBLIQUE)
    m_city_first = re.match(r'^([A-ZÀ-ÖØ-Þ\s\-]{3,})\s+(\d+[\w\s\-\.]+\s+(?:RUE|AVENUE|BOULEVARD|IMPASSE|CHEMIN|ROUTE|PLACE|ALLÉE|ALLEE|QUAI|CRS|CR|RES|RESIDENCE)\b.*)$', cleaned, re.IGNORECASE)
    if m_city_first:
        city = m_city_first.group(1).strip()
        street = m_city_first.group(2).strip()
        return f"{street}, {city}"

    # Fallback par slashs si présents
    parts = cleaned.split("/")
    if len(parts) >= 2:
        return " ".join([p.strip() for p in parts[1:]]).strip()

    return cleaned

def geocode_address(address):
    """Géocodage de l'adresse via la BAN (Base Adresse Nationale) pour obtenir lat/lon"""
    if not address:
        return None, None
    try:
        url = f"https://api-adresse.data.gouv.fr/search/?q={requests.utils.quote(address)}&limit=1"
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            data = r.json()
            if data.get("features"):
                coords = data["features"][0]["geometry"]["coordinates"]
                # Coordonnées au format [longitude, latitude]
                return coords[1], coords[0]
    except Exception as e:
        print(f"Erreur géocodage: {e}")
    return None, None

def send_telegram(ric_display, func, message, addr, is_urgent, is_test=False):
    cfg = get_config()
    token = cfg.get("telegram_bot_token", "")
    chat_id = cfg.get("telegram_chat_id", "")

    if not token or not chat_id:
        return False, "Telegram non configuré"

    header = "🧪 *TEST TELEGRAM - POCSAG*" if is_test else ("🚨 *ALERTE PRIORITAIRE POCSAG*" if is_urgent else "📋 *ALERTE POCSAG*")
    text = f"{header}\n\n📟 *RIC / Engin :* `{ric_display}`\n📌 *Sous-adresse :* `{func}`\n💬 *Message :* {message if message else '_Signal / Sans texte_'}\n"

    if addr:
        encoded_addr = requests.utils.quote(addr)
        text += f"\n📍 *Localisation :* {addr}\n🗺️ [Google Maps](https://www.google.com/maps/search/?api=1&query={encoded_addr})"

    try:
        # 1. Message texte Markdown
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
            "chat_id": chat_id, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": False
        }, timeout=5)

        # 2. Pin Maps géolocalisé
        if addr:
            lat, lon = geocode_address(addr)
            if lat and lon:
                requests.post(f"https://api.telegram.org/bot{token}/sendLocation", json={
                    "chat_id": chat_id, "latitude": lat, "longitude": lon
                }, timeout=5)
        return True, "OK"
    except Exception as e:
        return False, str(e)

def send_discord(ric, func, message, is_test=False):
    cfg = get_config()
    url = cfg.get("discord_webhook", "")
    if not url or "http" not in url:
        return False, "Webhook Discord non configuré"

    aliases = cfg.get("aliases", {})
    alias_name = aliases.get(str(ric), "")
    ric_display = f"{ric} ({alias_name})" if alias_name else str(ric)

    keywords = cfg.get("keywords", [])
    is_urgent = any(kw.lower() in message.lower() for kw in keywords) if message else False

    title = "🧪 Test Webhook Discord - POCSAG" if is_test else (f"🚨 ALERTE PRIORITAIRE — {ric_display}" if is_urgent else f"📋 Alerte POCSAG — {ric_display}")
    color = 5814783 if is_test else (15158332 if is_urgent else 3447003)

    fields = [
        {"name": "RIC / Capcode", "value": ric_display, "inline": True},
        {"name": "Sous-adresse", "value": str(func), "inline": True},
        {"name": "Message", "value": message if message else "*Signal / Sans texte*"}
    ]

    addr = extract_address(message)
    if addr:
        encoded_addr = requests.utils.quote(addr)
        gmaps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_addr}"
        fields.append({
            "name": "📍 Localisation",
            "value": f"**{addr}**\n🗺️ [Google Maps]({gmaps_url})",
            "inline": False
        })

    payload = {
        "content": "@everyone" if is_urgent and not is_test else "",
        "embeds": [{
            "title": title, "color": color, "fields": fields,
            "footer": {"text": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        }]
    }
    try:
        r = requests.post(url, json=payload, timeout=5)
        return (True, "OK") if r.status_code in [200, 204] else (False, f"HTTP {r.status_code}")
    except Exception as e:
        return False, str(e)

def process_notifications(ric, func, message, is_test=False):
    cfg = get_config()
    # Blacklist : aucune notification pour les RIC masqués
    if str(ric) in cfg.get("blacklist", []) and not is_test:
        return
    # notify_empty : ignorer les trames sans texte si désactivé
    if not message and not cfg.get("notify_empty", True) and not is_test:
        return
    aliases = cfg.get("aliases", {})
    alias_name = aliases.get(str(ric), "")
    ric_display = f"{ric} ({alias_name})" if alias_name else str(ric)
    keywords = cfg.get("keywords", [])
    is_urgent = any(kw.lower() in message.lower() for kw in keywords) if message else False
    addr = extract_address(message)

    send_discord(ric, func, message, is_test)
    send_telegram(ric_display, func, message, addr, is_urgent, is_test)

def save_to_web(ric, func, message):
    cfg = get_config()
    if str(ric) in cfg.get("blacklist", []):
        return

    addr = extract_address(message)
    # Géocodage pour mini-map OSM (BAN, timeout 3s) - n'ecrase pas le flux si échec
    lat, lon = (None, None)
    if addr:
        try:
            lat, lon = geocode_address(addr)
        except Exception:
            lat, lon = None, None

    entry = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "date": datetime.now().strftime("%d/%m/%Y"),
        "ric": str(ric),
        "alias": cfg.get("aliases", {}).get(str(ric), ""),
        "func": func,
        "message": message if message else "Signal / Sans texte",
        "address": addr,
        "lat": lat,
        "lon": lon
    }
    try:
        try:
            with open(LOG_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            data = []
        data.insert(0, entry)
        with open(LOG_FILE, "w") as f:
            json.dump(data[:300], f, indent=2)
    except Exception as e:
        print(f"Erreur log: {e}")

class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/config" or self.path.startswith("/api/config?"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(get_config()).encode())
        elif self.path == "/api/version" or self.path.startswith("/api/version?"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps({"version": get_version()}).encode())
        elif self.path == "/api/service/config" or self.path.startswith("/api/service/config?"):
            cfg = parse_service_file()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(cfg).encode())
        elif self.path == "/api/auth/verify" or self.path.startswith("/api/auth/verify?"):
            # Endpoint de vérification du mot de passe admin
            pwd = self.path.split("?pwd=")[1] if "?pwd=" in self.path else ""
            import urllib.parse
            pwd = urllib.parse.unquote(pwd)
            cfg = get_config()
            expected = cfg.get("admin_password", "admin")
            ok = (pwd == expected)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": ok}).encode())
        elif self.path == "/api/update/check" or self.path.startswith("/api/update/check?"):
            try:
                local_ver = get_version()
                r = requests.get("https://raw.githubusercontent.com/RouXx67/pocsag/main/VERSION", timeout=3)
                if r.status_code != 200:
                    r = requests.get("https://raw.githubusercontent.com/RouXx67/pocsag/master/VERSION", timeout=3)
                
                remote_ver = r.text.strip() if r.status_code == 200 else local_ver
                update_available = (local_ver != remote_ver and len(remote_ver) > 0)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"update_available": update_available, "local": local_ver, "remote": remote_ver}).encode())
            except Exception as e:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"update_available": False, "error": str(e)}).encode())
        elif self.path == "/api/logs" or self.path.startswith("/api/logs?"):
            try:
                import subprocess
                r = subprocess.run(
                    ["journalctl", "-u", "pocsag", "-n", "200", "--no-pager", "--output=short-iso"],
                    capture_output=True, text=True, timeout=5
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(r.stdout.encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(f"Erreur: {e}".encode())
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        # Normaliser le path (sans query string)
        path = self.path.split("?")[0]
        if path == "/api/config":
            try:
                cfg = json.loads(body) if body else {}
            except Exception:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":"invalid json"}')
                return
            save_config(cfg)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        elif path == "/api/clear-logs":
            try:
                with open(LOG_FILE, "w") as f:
                    json.dump([], f)
            except Exception as e:
                print(f"Erreur clear-logs: {e}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        elif path == "/api/test-discord":
            process_notifications("1234567", "1", "SAP VERT A DOMICILE VSAV001.COND BENFELD 7C RUE PETIT REMPART", True)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "message": "Tests envoyés"}).encode())
        elif path == "/api/service/restart":
            try:
                import subprocess
                # Répondre AVANT de redémarrer sinon la connexion est tuée par systemctl restart (le serveur HTTP est dans le service)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"restarting"}')
                try:
                    self.wfile.flush()
                except Exception:
                    pass
                def _delayed_restart():
                    import time as _t
                    _t.sleep(0.8)
                    try:
                        subprocess.run(["systemctl", "restart", "pocsag"], timeout=10)
                    except Exception as ex:
                        print(f"restart echoue: {ex}")
                threading.Thread(target=_delayed_restart, daemon=True).start()
            except Exception as e:
                try:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode())
                except Exception:
                    pass
            return
        elif path == "/api/service/status":
            try:
                import subprocess
                r = subprocess.run(["systemctl", "is-active", "pocsag"], capture_output=True, text=True, timeout=3)
                active = r.stdout.strip() == "active"
                freqs = get_config().get("frequencies", DEFAULT_FREQUENCIES)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"active": active, "frequencies": freqs}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return
        elif path == "/api/update/run":
            try:
                import subprocess
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"updating"}')
                try:
                    self.wfile.flush()
                except Exception:
                    pass
                def _delayed_update():
                    import time as _t
                    import os
                    _t.sleep(1)
                    try:
                        upd_script = "/opt/pocsag/update.sh"
                        if not os.path.exists(upd_script):
                            if os.path.exists("/home/pocsag/pocsag/update.sh"):
                                upd_script = "/home/pocsag/pocsag/update.sh"
                            else:
                                upd_script = "update.sh"
                        subprocess.run(["bash", upd_script, "--force"], timeout=30)
                    except Exception as ex:
                        print(f"update echoue: {ex}")
                threading.Thread(target=_delayed_update, daemon=True).start()
            except Exception as e:
                try:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode())
                except Exception:
                    pass
            return
        elif path == "/api/service/config":
            try:
                cfg = json.loads(body) if body else {}
            except Exception:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":"invalid json"}')
                return
            raw = cfg.get("raw", "").strip()
            if raw:
                service_content = raw
            else:
                config = get_config()
                freqs = config.get("frequencies", DEFAULT_FREQUENCIES)
                freq_args = " ".join(f"-f {f}" for f in freqs)
                squelch = cfg.get("squelch", 50)
                gain = cfg.get("gain", "19.2")
                sample_rate = cfg.get("sample_rate", "176400")
                output_rate = cfg.get("output_rate", "22050")
                restart = cfg.get("restart", "always")
                restart_sec = cfg.get("restart_sec", 5)
                description = cfg.get("description", "Decoder POCSAG RTL-SDR vers Web, Telegram et Discord")
                after = cfg.get("after", "network.target nginx.service")
                service_type = cfg.get("service_type", "simple")
                user = cfg.get("user", "root")
                exec_start = f'/bin/bash -c "rtl_fm {freq_args} -M fm -s {sample_rate} -r {output_rate} -E offset -l {squelch} -g {gain} | multimon-ng -t raw -a POCSAG512 -a POCSAG1200 -a POCSAG2400 -f alpha - | python3 /opt/pocsag/app.py"'
                service_content = f"""[Unit]
Description={description}
After={after}

[Service]
Type={service_type}
User={user}
ExecStart={exec_start}
Restart={restart}
RestartSec={restart_sec}

[Install]
WantedBy=multi-user.target
"""
            try:
                with open(SERVICE_FILE, "w") as f:
                    f.write(service_content)
                import subprocess
                subprocess.run(["systemctl", "daemon-reload"], timeout=5)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        return

threading.Thread(target=lambda: HTTPServer(("127.0.0.1", 8080), APIHandler).serve_forever(), daemon=True).start()

regex = re.compile(r"POCSAG\d+:\s+Address:\s+(\d+)\s+Function:\s+(\d+)(?:\s+Alpha:\s+(.*))?")
# Boucle résiliente : garde le serveur HTTP vivant même si stdin se ferme (rtl_fm crash)
import time
while True:
    try:
        for line in sys.stdin:
            match = regex.search(line)
            if match:
                ric, func, text = match.groups()
                text = text.strip() if text else ""
                try:
                    process_notifications(ric, func, text)
                except Exception as e:
                    print(f"Erreur notifications: {e}")
                try:
                    save_to_web(ric, func, text)
                except Exception as e:
                    print(f"Erreur save: {e}")
        # stdin EOF (rtl_fm arrêté) -> attendre avant de laisser systemd redémarrer
        print("Stdin fermé, attente 2s avant relecture...")
        time.sleep(2)
        # Si on arrive ici, le service va être redémarré par systemd ; on garde HTTP vivant
        # Ne pas quitter immédiatement pour éviter 502 nginx -> frontend JSON error
        time.sleep(5)
    except Exception as e:
        print(f"Erreur boucle principale: {e}")
        time.sleep(2)