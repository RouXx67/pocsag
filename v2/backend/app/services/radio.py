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
from app.services.parser import parse_line
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
                sample_rate = "176400"
                output_rate = "22050"
                rows = await session.execute(
                    select(ConfigEntry).where(
                        ConfigEntry.key.in_([
                            "frequencies", "scan_interval", "squelch",
                            "gain", "sample_rate", "output_rate",
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
            return {
                "freqs_str": freqs_str,
                "scan_interval": scan_interval,
                "squelch": squelch,
                "gain": gain,
                "sample_rate": sample_rate,
                "output_rate": output_rate,
            }

        return self._sync_call(_fetch()) or {
            "freqs_str": "",
            "scan_interval": settings.default_scan_interval,
            "squelch": 0,
            "gain": "19.2",
            "sample_rate": "176400",
            "output_rate": "22050",
        }

    def _run(self):
        global CURRENT_SCAN_FREQ
        while not self._stop.is_set():
            try:
                cfg = self._get_config()
                freqs_str = cfg["freqs_str"]
                scan_interval = cfg["scan_interval"]
                squelch = cfg["squelch"]
                gain = cfg["gain"]
                sample_rate = cfg["sample_rate"]
                output_rate = cfg["output_rate"]

                freqs = (
                    [f.strip() for f in freqs_str.split(",") if f.strip()]
                    if freqs_str
                    else settings.default_frequencies
                )

                if not freqs:
                    time.sleep(5)
                    continue

                preexec = getattr(os, 'setsid', None)
                can_killpg = preexec is not None

                for freq in freqs:
                    if self._stop.is_set():
                        break

                    with _scan_freq_lock:
                        CURRENT_SCAN_FREQ = freq
                    log.info("[Scanner] %s (%ds)", freq, scan_interval)

                    rtl_args = [
                        "rtl_fm",
                        "-f", freq,
                        "-M", "fm",
                        "-s", str(sample_rate),
                        "-r", str(output_rate),
                        "-E", "offset",
                        "-l", str(squelch),
                        "-g", str(gain),
                    ]
                    mm_args = [
                        "multimon-ng",
                        "-t", "raw",
                        "-a", "POCSAG512",
                        "-a", "POCSAG1200",
                        "-a", "POCSAG2400",
                        "-f", "alpha",
                        "-",
                    ]

                    try:
                        rtl_proc = subprocess.Popen(
                            rtl_args,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL,
                            preexec_fn=preexec,
                        )
                        mm_proc = subprocess.Popen(
                            mm_args,
                            stdin=rtl_proc.stdout,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL,
                            text=True,
                            preexec_fn=preexec,
                        )
                        rtl_proc.stdout.close()
                    except Exception as e:
                        log.error("[Scanner] Demarrage: %s", e)
                        time.sleep(2)
                        continue

                    stop_reader = threading.Event()

                    def _read_output():
                        try:
                            for line in iter(mm_proc.stdout.readline, ''):
                                if stop_reader.is_set():
                                    break
                                line = line.strip()
                                if line:
                                    parsed = parse_line(line)
                                    if parsed:
                                        self._call_on_message(parsed)
                        except Exception:
                            pass

                    reader = threading.Thread(target=_read_output, daemon=True)
                    reader.start()

                    # Ecoute pendant scan_interval (ou jusqu'a l'arret)
                    start_t = time.time()
                    while time.time() - start_t < scan_interval:
                        if self._stop.is_set() or mm_proc.poll() is not None:
                            break
                        time.sleep(0.5)

                    stop_reader.set()
                    _kill_process_group(mm_proc, can_killpg)
                    _kill_process_group(rtl_proc, can_killpg)
                    time.sleep(0.5)

            except Exception as e:
                log.error("[Scanner] Boucle: %s", e)
                time.sleep(2)