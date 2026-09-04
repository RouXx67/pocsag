import sys
import re
import json
import requests
import threading
import os
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("pocsag")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.environ.get("POCSAG_CONFIG", os.path.join(BASE_DIR, "config.json"))
LOG_FILE = os.environ.get("POCSAG_LOG", os.path.join(BASE_DIR, "..", "www", "data.json"))
SERVICE_FILE = "/etc/systemd/system/pocsag.service"
VERSION_FILE = os.path.join(os.path.dirname(BASE_DIR), "VERSION")
DEFAULT_FREQUENCIES = ["85.955M", "173512.5k"]
FREQ_MAX = 3
SCAN_INTERVAL_MIN = 5
HTTP_PORT = 8080
HTTP_HOST = "127.0.0.1"
LOG_MAX_ENTRIES = 300
GEOCODE_TIMEOUT = 3
FREQ_RE = re.compile(r"^\s*\d+(\.\d+)?\s*[kKmM]?(?:Hz)?\s*$")
POCSAG_RE = re.compile(r"POCSAG\d+:\s+Address:\s+(\d+)\s+Function:\s+(\d+)(?:\s+Alpha:\s+(.*))?")

_config_lock = threading.Lock()
_scan_freq_lock = threading.Lock()
CURRENT_SCAN_FREQ = None


def get_version():
    for path in [VERSION_FILE, os.path.join(BASE_DIR, "VERSION")]:
        try:
            with open(path, "r") as f:
                return f.read().strip()
        except Exception:
            continue
    return "1.0.0"


def parse_service_file():
    result = {
        "description": "Decoder POCSAG RTL-SDR vers Web, Telegram et Discord",
        "after": "network.target nginx.service",
        "service_type": "simple",
        "user": "root",
        "squelch": 0,
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
                try:
                    result["restart_sec"] = int(line.split("=", 1)[1])
                except ValueError:
                    pass
            elif line.startswith("ExecStart="):
                exec_start = line.split("=", 1)[1]
                m = re.search(r'rtl_fm\s+(.*?)\s*\|', exec_start)
                if m:
                    rtl_args = m.group(1)
                    sl = re.search(r'-l\s+(\S+)', rtl_args)
                    if sl:
                        try:
                            result["squelch"] = int(sl.group(1))
                        except ValueError:
                            pass
                    g = re.search(r'-g\s+(\S+)', rtl_args)
                    if g:
                        result["gain"] = g.group(1)
                    s = re.search(r'-s\s+(\S+)', rtl_args)
                    if s:
                        result["sample_rate"] = s.group(1)
                    rm = re.search(r'-r\s+(\S+)', rtl_args)
                    if rm:
                        result["output_rate"] = rm.group(1)
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
    "scan_interval": 30,
    "admin_password": "admin"
}


def get_config():
    with _config_lock:
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
                if "frequencies" not in cfg:
                    cfg["frequencies"] = DEFAULT_FREQUENCIES.copy()
                return cfg
        except Exception:
            return DEFAULT_CONFIG.copy()


def save_config(cfg):
    with _config_lock:
        if "service" not in cfg:
            old_cfg = get_config()
            if "service" in old_cfg:
                cfg["service"] = old_cfg["service"]
        if "frequencies" in cfg:
            cfg["frequencies"] = normalize_frequencies(cfg["frequencies"])
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                json.dump(cfg, f, indent=2)
        except Exception as e:
            log.error("Erreur sauvegarde config: %s", e)
        try:
            update_pocsag_service(cfg.get("frequencies", DEFAULT_FREQUENCIES))
        except Exception as e:
            log.error("Erreur update service: %s", e)


def normalize_frequencies(freqs):
    if not isinstance(freqs, list):
        return DEFAULT_FREQUENCIES.copy()
    cleaned = []
    for f in freqs:
        if not isinstance(f, str):
            f = str(f)
        f = f.strip()
        if not f:
            continue
        if FREQ_RE.match(f):
            f = re.sub(r"\s+", "", f)
            cleaned.append(f)
        if len(cleaned) >= FREQ_MAX:
            break
    return cleaned if cleaned else DEFAULT_FREQUENCIES.copy()


def update_pocsag_service(frequencies=None):
    cfg = get_config()
    svc = cfg.get("service", {})
    restart = svc.get("restart", "always")
    restart_sec = svc.get("restart_sec", 5)
    description = svc.get("description", "Decoder POCSAG RTL-SDR vers Web, Telegram et Discord")
    after = svc.get("after", "network.target nginx.service")
    service_type = svc.get("service_type", "simple")
    user = svc.get("user", "root")
    python_bin = sys.executable or "/usr/bin/python3"
    exec_start = f"{python_bin} {os.path.join(BASE_DIR, 'app.py')}"
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
    try:
        with open(SERVICE_FILE, "r") as f:
            existing = f.read()
        if existing == content:
            return True
    except Exception:
        pass
    try:
        with open(SERVICE_FILE, "w") as f:
            f.write(content)
        import subprocess
        subprocess.run(["systemctl", "daemon-reload"], timeout=5)
    except Exception as e:
        log.error("daemon-reload: %s", e)
    return True


def extract_address(message):
    if not message:
        return ""

    cleaned = message
    for prefix in ["AVP", "SAP", "FEU", "SECOURS", "INTERVENTION", "VL CONTRE ARBRE", "PL CONTRE ARBRE", "DEGAGEMENT", "RECONNAISSANCE"]:
        if cleaned.upper().startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()

    cleaned = re.sub(r'\b[A-Z]{3,}\d{3}(?:\.[A-Z0-9]+)?\s*', '', cleaned)
    cleaned = cleaned.strip()

    m_city_first = re.match(r'^([A-ZÀ-ÖØ-Þ\s\-]{3,})\s+(\d+[\w\s\-\.]+\s+(?:RUE|AVENUE|BOULEVARD|IMPASSE|CHEMIN|ROUTE|PLACE|ALLÉE|ALLEE|QUAI|CRS|CR|RES|RESIDENCE)\b.*)$', cleaned, re.IGNORECASE)
    if m_city_first:
        city = m_city_first.group(1).strip()
        street = m_city_first.group(2).strip()
        return f"{street}, {city}"

    parts = cleaned.split("/")
    if len(parts) >= 2:
        return " ".join([p.strip() for p in parts[1:]]).strip()
    return cleaned


def geocode_address(address):
    if not address:
        return None, None
    try:
        url = f"https://api-adresse.data.gouv.fr/search/?q={requests.utils.quote(address)}&limit=1"
        r = requests.get(url, timeout=GEOCODE_TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            if data.get("features"):
                coords = data["features"][0]["geometry"]["coordinates"]
                return coords[1], coords[0]
    except Exception as e:
        log.warning("Erreur géocodage: %s", e)
    return None, None


def send_telegram(ric_display, func, message, addr, is_urgent, is_test=False):
    cfg = get_config()
    token = cfg.get("telegram_bot_token", "")
    chat_id = cfg.get("telegram_chat_id", "")

    if not token or not chat_id:
        return False, "Telegram non configuré"

    header = "TEST TELEGRAM - POCSAG" if is_test else ("ALERTE PRIORITAIRE POCSAG" if is_urgent else "ALERTE POCSAG")
    text = f"*{header}*\n\n*RIC / Engin :* `{ric_display}`\n*Sous-adresse :* `{func}`\n*Message :* {message if message else '_Signal / Sans texte_'}\n"

    if addr:
        encoded_addr = requests.utils.quote(addr)
        text += f"\n*Localisation :* {addr}\n[Google Maps](https://www.google.com/maps/search/?api=1&query={encoded_addr})"

    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
            "chat_id": chat_id, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": False
        }, timeout=5)
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

    title = "Test Webhook Discord - POCSAG" if is_test else (f"ALERTE PRIORITAIRE - {ric_display}" if is_urgent else f"Alerte POCSAG - {ric_display}")
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
            "name": "Localisation",
            "value": f"**{addr}**\n[Google Maps]({gmaps_url})",
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
    if str(ric) in cfg.get("blacklist", []) and not is_test:
        return
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
    lat, lon = None, None
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
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "w") as f:
            json.dump(data[:LOG_MAX_ENTRIES], f, indent=2)
    except Exception as e:
        log.error("Erreur log: %s", e)


class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/config" or self.path.startswith("/api/config?"):
            self._json_response(200, get_config())
        elif self.path == "/api/version" or self.path.startswith("/api/version?"):
            self._json_response(200, {"version": get_version()})
        elif self.path == "/api/service/config" or self.path.startswith("/api/service/config?"):
            self._json_response(200, parse_service_file())
        elif self.path.startswith("/api/auth/verify?"):
            pwd = self.path.split("?pwd=")[1] if "?pwd=" in self.path else ""
            import urllib.parse
            pwd = urllib.parse.unquote(pwd)
            cfg = get_config()
            expected = cfg.get("admin_password", "admin")
            self._json_response(200, {"success": pwd == expected})
        elif self.path == "/api/update/check" or self.path.startswith("/api/update/check?"):
            try:
                local_ver = get_version()
                r = requests.get("https://raw.githubusercontent.com/RouXx67/pocsag/main/VERSION", timeout=3)
                if r.status_code != 200:
                    r = requests.get("https://raw.githubusercontent.com/RouXx67/pocsag/master/VERSION", timeout=3)
                remote_ver = r.text.strip() if r.status_code == 200 else local_ver
                update_available = (local_ver != remote_ver and len(remote_ver) > 0)
                self._json_response(200, {"update_available": update_available, "local": local_ver, "remote": remote_ver})
            except Exception as e:
                self._json_response(200, {"update_available": False, "error": str(e)})
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
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(f"Erreur de r\u00e9cup\u00e9ration des logs: {e}".encode())
        else:
            self.send_error(404)

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        path = self.path.split("?")[0]

        handlers = {
            "/api/config": self._handle_config,
            "/api/clear-logs": self._handle_clear_logs,
            "/api/test-discord": self._handle_test_discord,
            "/api/service/restart": self._handle_service_restart,
            "/api/service/status": self._handle_service_status,
            "/api/update/run": self._handle_update_run,
            "/api/service/config": self._handle_service_config,
        }

        handler = handlers.get(path)
        if handler:
            handler(body)
        else:
            self.send_error(404)

    def _handle_config(self, body):
        try:
            cfg = json.loads(body) if body else {}
        except Exception:
            self._json_response(400, {"error": "invalid json"})
            return
        save_config(cfg)
        self._json_response(200, {"status": "ok"})

    def _handle_clear_logs(self, body):
        try:
            os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
            with open(LOG_FILE, "w") as f:
                json.dump([], f)
        except Exception as e:
            log.error("Erreur clear-logs: %s", e)
        self._json_response(200, {"status": "ok"})

    def _handle_test_discord(self, body):
        process_notifications("1234567", "1", "SAP VERT A DOMICILE VSAV001.COND BENFELD 7C RUE PETIT REMPART", True)
        self._json_response(200, {"success": True, "message": "Tests envoy\u00e9s"})

    def _handle_service_restart(self, body):
        try:
            import subprocess
            self._json_response(200, {"status": "restarting"})
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
                    log.error("restart echoue: %s", ex)
            threading.Thread(target=_delayed_restart, daemon=True).start()
        except Exception as e:
            try:
                self._json_response(500, {"error": str(e)})
            except Exception:
                pass

    def _handle_service_status(self, body):
        try:
            import subprocess
            r = subprocess.run(["systemctl", "is-active", "pocsag"], capture_output=True, text=True, timeout=3)
            active = r.stdout.strip() == "active"
            freqs = get_config().get("frequencies", DEFAULT_FREQUENCIES)
            with _scan_freq_lock:
                current_freq = CURRENT_SCAN_FREQ
            self._json_response(200, {
                "active": active,
                "frequencies": freqs,
                "current_freq": current_freq
            })
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    def _handle_update_run(self, body):
        try:
            import subprocess
            self._json_response(200, {"status": "updating"})
            try:
                self.wfile.flush()
            except Exception:
                pass

            def _delayed_update():
                import time as _t
                _t.sleep(1)
                try:
                    upd_script = None
                    for candidate in [
                        "/opt/pocsag/update.sh",
                        "/home/pocsag/pocsag/update.sh",
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), "update.sh"),
                        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "update.sh")
                    ]:
                        if os.path.exists(candidate):
                            upd_script = candidate
                            break

                    if not upd_script:
                        try:
                            res_find = subprocess.run(["find", "/", "-name", "update.sh", "-type", "f"], capture_output=True, text=True, timeout=5)
                            found = res_find.stdout.strip().split("\n")
                            if found and found[0]:
                                upd_script = found[0]
                        except Exception:
                            pass

                    if upd_script and os.path.exists(upd_script):
                        subprocess.run(["bash", upd_script, "--force"], timeout=60)
                    else:
                        log.warning("Script update.sh introuvable sur le syst\u00e8me")
                except Exception as ex:
                    log.error("update echoue: %s", ex)
            threading.Thread(target=_delayed_update, daemon=True).start()
        except Exception as e:
            try:
                self._json_response(500, {"error": str(e)})
            except Exception:
                pass

    def _handle_service_config(self, body):
        try:
            cfg = json.loads(body) if body else {}
        except Exception:
            self._json_response(400, {"error": "invalid json"})
            return
        raw = cfg.get("raw", "").strip()
        if raw:
            service_content = raw
        else:
            config = get_config()
            freqs = config.get("frequencies", DEFAULT_FREQUENCIES)
            freq_args = " ".join(f"-f {f}" for f in freqs)
            squelch = cfg.get("squelch", 0)
            gain = cfg.get("gain", "19.2")
            sample_rate = cfg.get("sample_rate", "176400")
            output_rate = cfg.get("output_rate", "22050")
            restart = cfg.get("restart", "always")
            restart_sec = cfg.get("restart_sec", 5)
            description = cfg.get("description", "Decoder POCSAG RTL-SDR vers Web, Telegram et Discord")
            after = cfg.get("after", "network.target nginx.service")
            service_type = cfg.get("service_type", "simple")
            user = cfg.get("user", "root")
            exec_start = f'/bin/bash -c "rtl_fm {freq_args} -M fm -s {sample_rate} -r {output_rate} -E offset -l {squelch} -g {gain} | multimon-ng -t raw -a POCSAG512 -a POCSAG1200 -a POCSAG2400 -f alpha - | python3 {os.path.join(BASE_DIR, "app.py")}"'
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
            self._json_response(200, {"status": "ok"})
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    def log_message(self, format, *args):
        pass


def handle_pocsag_line(line):
    if not line:
        return
    match = POCSAG_RE.search(line)
    if match:
        ric, func, text = match.groups()
        text = text.strip() if text else ""
        try:
            process_notifications(ric, func, text)
        except Exception as e:
            log.error("Erreur notifications: %s", e)
        try:
            save_to_web(ric, func, text)
        except Exception as e:
            log.error("Erreur save: %s", e)


def stdin_listener():
    try:
        if sys.stdin and not sys.stdin.isatty():
            for line in sys.stdin:
                handle_pocsag_line(line)
    except Exception:
        pass


def radio_scanner_loop():
    global CURRENT_SCAN_FREQ
    import signal
    import subprocess
    import time

    while True:
        try:
            cfg = get_config()
            freqs = cfg.get("frequencies", DEFAULT_FREQUENCIES)
            if not freqs:
                time.sleep(5)
                continue

            svc = cfg.get("service", {})
            squelch = svc.get("squelch", 0)
            gain = svc.get("gain", "19.2")
            sample_rate = svc.get("sample_rate", "176400")
            output_rate = svc.get("output_rate", "22050")
            scan_interval = int(cfg.get("scan_interval", 30))
            if scan_interval < SCAN_INTERVAL_MIN:
                scan_interval = SCAN_INTERVAL_MIN

            for freq in freqs:
                with _scan_freq_lock:
                    CURRENT_SCAN_FREQ = freq

                rtl_args = ["rtl_fm", "-f", freq, "-M", "fm", "-s", str(sample_rate), "-r", str(output_rate), "-E", "offset", "-l", str(squelch), "-g", str(gain)]
                mm_args = ["multimon-ng", "-t", "raw", "-a", "POCSAG512", "-a", "POCSAG1200", "-a", "POCSAG2400", "-f", "alpha", "-"]

                log.info("[Radio Scanner] %coute sur %s (dur%e: %ds, squelch: %s, gain: %s)",
                         "É", freq, "é", scan_interval, squelch, gain)

                preexec = getattr(os, 'setsid', None)
                try:
                    rtl_proc = subprocess.Popen(
                        rtl_args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        preexec_fn=preexec
                    )
                    mm_proc = subprocess.Popen(
                        mm_args,
                        stdin=rtl_proc.stdout,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True,
                        preexec_fn=preexec
                    )
                    rtl_proc.stdout.close()
                    proc = mm_proc
                except Exception as e:
                    log.error("[Radio Scanner] Erreur d%e9marrage: %s", "é", e)
                    time.sleep(2)
                    continue

                stop_reader = threading.Event()

                def _read_output():
                    try:
                        for line in iter(proc.stdout.readline, ''):
                            if stop_reader.is_set():
                                break
                            handle_pocsag_line(line)
                    except Exception:
                        pass

                reader = threading.Thread(target=_read_output, daemon=True)
                reader.start()

                if len(freqs) == 1:
                    proc.wait()
                    stop_reader.set()
                    time.sleep(1)
                else:
                    start_t = time.time()
                    while time.time() - start_t < scan_interval:
                        if proc.poll() is not None:
                            break
                        time.sleep(1)

                    stop_reader.set()
                    _kill_process_group(proc, preexec is not None)
                    _kill_process_group(rtl_proc, preexec is not None)
                    time.sleep(0.5)

        except Exception as ex:
            log.error("[Radio Scanner] Exception boucle: %s", ex)
            time.sleep(2)


def _kill_process_group(proc, can_killpg):
    import signal
    import subprocess
    try:
        if can_killpg:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
            proc.wait(timeout=2)
        else:
            proc.terminate()
            proc.wait(timeout=2)
    except Exception:
        try:
            if can_killpg:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            else:
                proc.kill()
        except Exception:
            pass


threading.Thread(target=lambda: HTTPServer((HTTP_HOST, HTTP_PORT), APIHandler).serve_forever(), daemon=True).start()
threading.Thread(target=stdin_listener, daemon=True).start()

try:
    update_pocsag_service()
except Exception:
    pass

radio_scanner_loop()