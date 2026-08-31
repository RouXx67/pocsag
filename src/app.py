import sys
import re
import json
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

CONFIG_FILE = "/opt/pocsag/config.json"
LOG_FILE = "/var/www/html/data.json"

def get_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {
            "discord_webhook": "",
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            "notify_empty": True,
            "aliases": {},
            "blacklist": [],
            "keywords": ["AVP", "FEU", "DESINCARCERATION", "RENFORT", "URGENT"]
        }

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def extract_address(message):
    if not message:
        return ""
    
    # 1. Découpage après l'engin et son rôle (ex: VSAV001.COND BENFELD 7C RUE PETIT REMPART)
    match = re.search(r'\b[A-Z0-9]+\.[A-Z0-9]+\s+(.*)', message)
    if match:
        return match.group(1).strip()

    # Variante pour engins sans point dans le rôle (ex: VSAV001 BENFELD...)
    match_alt = re.search(r'\b[A-Z]{3,}\d{3}\s+(.*)', message)
    if match_alt:
        return match_alt.group(1).strip()

    # 2. Fallback pour découpage par slashs (ex: AVP / BENFELD / RUE PETIT REMPART)
    parts = message.split("/")
    if len(parts) >= 2:
        return " ".join([p.strip() for p in parts[1:]]).strip()

    return message.strip()

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
        osm_url = f"https://www.openstreetmap.org/search?query={encoded_addr}"
        fields.append({
            "name": "📍 Localisation",
            "value": f"**{addr}**\n🗺️ [Google Maps]({gmaps_url}) | 🌍 [OpenStreetMap]({osm_url})",
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

    entry = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "date": datetime.now().strftime("%d/%m/%Y"),
        "ric": str(ric),
        "alias": cfg.get("aliases", {}).get(str(ric), ""),
        "func": func,
        "message": message if message else "Signal / Sans texte",
        "address": extract_address(message)
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
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        return

threading.Thread(target=lambda: HTTPServer(("127.0.0.1", 8080), APIHandler).serve_forever(), daemon=True).start()

regex = re.compile(r"POCSAG\d+:\s+Address:\s+(\d+)\s+Function:\s+(\d+)(?:\s+Alpha:\s+(.*))?")
for line in sys.stdin:
    match = regex.search(line)
    if match:
        ric, func, text = match.groups()
        text = text.strip() if text else ""
        process_notifications(ric, func, text)
        save_to_web(ric, func, text)