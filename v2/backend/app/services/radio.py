from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from typing import Optional

from app.config import settings
from app.database import async_session_factory
from app.models import ConfigEntry
from app.services.parser import parse_line
from sqlalchemy import select

log = logging.getLogger("pocsag.radio")

CURRENT_SCAN_FREQ: Optional[str] = None


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


def _kill_proc(proc):
    if proc is None or proc.returncode is not None:
        return
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, 15)
        proc.wait(2)
    except Exception:
        try:
            os.killpg(pgid, 9)
        except Exception:
            pass


class RadioScanner:
    def __init__(self, on_message):
        self._rtl_proc: Optional[asyncio.subprocess.Process] = None
        self._mm_proc: Optional[asyncio.subprocess.Process] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.on_message = on_message

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        if self._running:
            return
        subprocess.run(["pkill", "-9", "rtl_fm"], capture_output=True, timeout=3)
        subprocess.run(["pkill", "-9", "multimon-ng"], capture_output=True, timeout=3)
        ok, msg = check_dongle()
        if not ok:
            log.warning("Dongle: %s", msg)
        else:
            log.info("Dongle OK")
        self._running = True
        self._task = asyncio.get_event_loop().create_task(self._loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._kill_all()

    async def restart(self):
        await self.stop()
        self.start()

    async def _loop(self):
        global CURRENT_SCAN_FREQ
        while self._running:
            try:
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

                freqs = (
                    [f.strip() for f in freqs_str.split(",") if f.strip()]
                    if freqs_str
                    else settings.default_frequencies
                )

                if not freqs:
                    await asyncio.sleep(5)
                    continue

                for freq in freqs:
                    if not self._running:
                        break

                    CURRENT_SCAN_FREQ = freq
                    log.info("[Scanner] %s (%ds)", freq, scan_interval)

                    try:
                        await self._scan_frequency(
                            freq, squelch, gain, sample_rate, output_rate, scan_interval
                        )
                    except Exception as e:
                        log.error("[Scanner] Error %s: %s", freq, e)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("[Scanner] Loop: %s", e)
                await asyncio.sleep(2)

    async def _scan_frequency(
        self, freq, squelch, gain, sample_rate, output_rate, duration
    ):
        """Same approach as V1: separate subprocesses, no stderr capture (avoids pipe deadlock)."""
        preexec = getattr(os, 'setsid', None)

        try:
            self._rtl_proc = await asyncio.create_subprocess_exec(
                "rtl_fm",
                "-f", freq,
                "-M", "fm",
                "-s", str(sample_rate),
                "-r", str(output_rate),
                "-E", "offset",
                "-l", str(squelch),
                "-g", str(gain),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                preexec_fn=preexec,
            )
            self._mm_proc = await asyncio.create_subprocess_exec(
                "multimon-ng",
                "-t", "raw",
                "-a", "POCSAG512",
                "-a", "POCSAG1200",
                "-a", "POCSAG2400",
                "-f", "alpha",
                "-",
                stdin=self._rtl_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                preexec_fn=preexec,
            )
            if self._rtl_proc.stdout:
                self._rtl_proc.stdout.close()
        except Exception as e:
            log.error("[Scanner] Subprocess start failed: %s", e)
            return

        try:
            while self._running:
                try:
                    raw = await asyncio.wait_for(
                        self._mm_proc.stdout.readline(), timeout=1
                    )
                except asyncio.TimeoutError:
                    continue
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    parsed = parse_line(line)
                    if parsed and self.on_message:
                        asyncio.create_task(self.on_message(parsed))
        except Exception:
            pass

        self._kill_all()
        await asyncio.sleep(0.3)

    def _kill_all(self):
        _kill_proc(self._mm_proc)
        _kill_proc(self._rtl_proc)
        self._mm_proc = None
        self._rtl_proc = None