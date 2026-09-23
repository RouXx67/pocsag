from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import threading
import time
from typing import Optional

from app.config import settings
from app.database import async_session_factory
from app.models import ConfigEntry
from app.services.parser import POCSAGParser, parse_line
from sqlalchemy import select

log = logging.getLogger("pocsag.radio")

CURRENT_SCAN_FREQ: Optional[str] = None
_scan_freq_lock = threading.Lock()


def check_dongle() -> tuple[bool, str]:
    try:
        r = subprocess.run(["lsusb"], capture_output=True, timeout=3)
        out = r.stdout.decode("utf-8", errors="replace")
        if any(x in out for x in ["0bda:2832", "0bda:2838", "RTL2832", "RTL2838", "Realtek"]):
            return True, "Cle RTL-SDR detectee (lsusb)"
        return False, "Aucun dongle detecte (lsusb)"
    except FileNotFoundError:
        return False, "lsusb introuvable"
    except Exception as e:
        return False, str(e)


def _kill_process_group(proc, can_killpg):
    if proc is None:
        return
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


class RadioScanner:
    """Scanner radio dans un thread dedie, utilisant subprocess.Popen
    (meme approche que la V1 qui fonctionnait). Le callback on_message
    est planifie sur la boucle asyncio principale via run_coroutine_threadsafe."""

    def __init__(self, on_message):
        self.on_message = on_message
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def set_loop(self, loop):
        self._loop = loop

    def start(self):
        if self.is_running:
            return
        subprocess.run(["pkill", "-9", "rtl_fm"], capture_output=True, timeout=3)
        subprocess.run(["pkill", "-9", "multimon-ng"], capture_output=True, timeout=3)
        ok, msg = check_dongle()
        if not ok:
            log.warning("Dongle: %s", msg)
        else:
            log.info("Dongle OK")
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="radio-scanner")
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _call_on_message(self, parsed):
        if self._loop is None or self.on_message is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self.on_message(parsed), self._loop)
        except Exception:
            pass

    def _sync_call(self, coro):
        """Execute une coroutine sur la boucle principale et bloque ce thread."""
        if self._loop is None:
            return None
        try:
            fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
            return fut.result(timeout=10)
        except Exception as e:
            log.error("[Scanner] sync_call: %s", e)
            return None

    def _get_config(self):
        async def _fetch():
            async with async_session_factory() as session:
                freqs_str = ""
                scan_interval = settings.default_scan_interval
                squelch = 0
                gain = "19.2"
                sample_rate = "22050"
                output_rate = "22050"
                bias_t = False
                rows = await session.execute(
                    select(ConfigEntry).where(
                        ConfigEntry.key.in_([
                            "frequencies", "scan_interval", "squelch",
                            "gain", "sample_rate", "output_rate", "bias_t",
                        ])
                    )
                )
                for row in rows.scalars():
                    if row.key == "frequencies":
                        freqs_str = row.value
                    elif row.key == "scan_interval":
                        try:
                            scan_interval = max(int(row.value), settings.scan_interval_min)
                        except ValueError:
                            pass
                    elif row.key == "squelch":
                        try:
                            squelch = int(row.value)
                        except ValueError:
                            pass
                    elif row.key == "gain":
                        gain = row.value
                    elif row.key == "sample_rate":
                        sample_rate = row.value
                    elif row.key == "output_rate":
                        output_rate = row.value
                    elif row.key == "bias_t":
                        bias_t = row.value.lower() in ("true", "yes", "1")
            # Extraire la première fréquence (ou utiliser la default)
            raw_freqs = [f.strip() for f in freqs_str.split(",") if f.strip()] if freqs_str else []
            frequency = raw_freqs[0] if raw_freqs else settings.default_frequencies[0]
            return {
                "frequency": frequency,
                "scan_interval": scan_interval,
                "squelch": squelch,
                "gain": gain,
                "sample_rate": sample_rate,
                "output_rate": output_rate,
                "bias_t": bias_t,
            }

        return self._sync_call(_fetch()) or {
            "frequency": settings.default_frequencies[0],
            "scan_interval": settings.default_scan_interval,
            "squelch": 0,
            "gain": "19.2",
            "sample_rate": "22050",
            "output_rate": "22050",
            "bias_t": False,
        }

    def _run(self):
        global CURRENT_SCAN_FREQ
        log.info("[Scanner] Démarrage (écoute continue fréquence unique)")
        while not self._stop.is_set():
            try:
                cfg = self._get_config()
                frequency = cfg["frequency"]
                squelch = cfg["squelch"]
                gain = cfg["gain"]
                sample_rate = cfg["sample_rate"]
                output_rate = cfg["output_rate"]
                bias_t = cfg["bias_t"]

                with _scan_freq_lock:
                    CURRENT_SCAN_FREQ = frequency
                log.info("[Scanner] Fréquence d'écoute : %s", frequency)

                preexec = getattr(os, 'setsid', None)
                can_killpg = preexec is not None

                # Construction de la commande rtl_fm (style F4JTV)
                rtl_args = ["rtl_fm"]
                if bias_t:
                    rtl_args.append("-T")
                rtl_args.extend(["-f", frequency])
                rtl_args.extend(["-g", gain])
                rtl_args.extend(["-s", sample_rate])
                if squelch:
                    rtl_args.extend(["-l", str(squelch)])
                rtl_args.append("-")  # stdout

                # Construction de la commande multimon-ng (style F4JTV)
                mm_args = [
                    "multimon-ng",
                    "-t", "raw",
                    "-a", "POCSAG512",
                    "-a", "POCSAG1200",
                    "-a", "POCSAG2400",
                    "-",
                ]

                try:
                    log.debug("[Scanner] Commande rtl_fm : %s", " ".join(rtl_args))
                    log.debug("[Scanner] Commande multimon-ng : %s", " ".join(mm_args))
                    rtl_proc = subprocess.Popen(
                        rtl_args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        preexec_fn=preexec,
                        text=False,
                    )
                    mm_proc = subprocess.Popen(
                        mm_args,
                        stdin=rtl_proc.stdout,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True,
                        preexec_fn=preexec,
                    )
                    rtl_proc.stdout.close()  # permet que rtl_fm voit SIGPIPE si multimon-ng meurt
                except Exception as e:
                    log.error("[Scanner] Démmarrage pipeline: %s", e)
                    time.sleep(2)
                    continue

                parser = POCSAGParser()
                stop_reader = threading.Event()

                def _read_output():
                    try:
                        for line in iter(mm_proc.stdout.readline, ''):
                            if stop_reader.is_set():
                                break
                            line = line.rstrip("\n")
                            if not line:
                                continue
                            # Utiliser le parser stateful
                            parsed = parser.feed(line)
                            if parsed:
                                self._call_on_message(parsed)
                    except Exception as e:
                        log.error("[Scanner] Lecture sortie: %s", e)
                    finally:
                        # À la fin du flux (multimon-ng arrêté), forcer un flush des messages en attente
                        pending = parser.flush()
                        if pending:
                            self._call_on_message(pending)

                reader = threading.Thread(target=_read_output, daemon=True)
                reader.start()

                # Surveillance continue jusqu'à arrêt ou mort du pipeline
                while not self._stop.is_set():
                    if mm_proc.poll() is not None:
                        log.warning("[Scanner] multimon-ng terminé avec code %s, redémarrage...",
                                    mm_proc.returncode)
                        break
                    time.sleep(1)

                # Nettoyage
                stop_reader.set()
                _kill_process_group(mm_proc, can_killpg)
                _kill_process_group(rtl_proc, can_killpg)
                time.sleep(1)  # Anti-lock USB

            except Exception as e:
                log.error("[Scanner] Boucle: %s", e)
                time.sleep(2)