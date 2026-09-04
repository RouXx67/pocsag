from __future__ import annotations

import asyncio
import logging
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
    """Teste si la clé RTL-SDR est détectée via rtl_test."""
    try:
        r = subprocess.run(
            ["rtl_test", "-t", "-s", "1M"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 or "Found" in r.stdout:
            return True, "Clé RTL-SDR détectée"
        return False, r.stderr.strip() or r.stdout.strip() or "Aucune clé détectée"
    except FileNotFoundError:
        return False, "rtl_test introuvable (rtl-sdr non installé)"
    except subprocess.TimeoutExpired:
        return False, "Timeout sur rtl_test (clé occupée ?)"
    except Exception as e:
        return False, str(e)


class RadioScanner:
    def __init__(self, on_message):
        self._process: Optional[asyncio.subprocess.Process] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.on_message = on_message

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self):
        if self._running:
            return

        # Tuer tout processus rtl_fm résiduel avant de commencer
        try:
            subprocess.run(["pkill", "-9", "rtl_fm"], capture_output=True, timeout=3)
            subprocess.run(["pkill", "-9", "multimon-ng"], capture_output=True, timeout=3)
        except Exception:
            pass
        await asyncio.sleep(0.5)

        ok, msg = check_dongle()
        if not ok:
            log.warning("RTL-SDR dongle check failed: %s", msg)
            log.warning("Scanner will retry on next loop")
        else:
            log.info("RTL-SDR dongle OK")

        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._kill_processes()

    async def restart(self):
        await self.stop()
        await self.start()

    async def _loop(self):
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

                    global CURRENT_SCAN_FREQ
                    CURRENT_SCAN_FREQ = freq
                    log.info("Scanning %s for %ds", freq, scan_interval)

                    try:
                        await self._scan_frequency(
                            freq, squelch, gain, sample_rate, output_rate, scan_interval
                        )
                    except Exception as e:
                        log.error("Error scanning %s: %s", freq, e)

                    if len(freqs) > 1:
                        await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Radio loop error: %s", e)
                await asyncio.sleep(2)

    async def _scan_frequency(
        self, freq, squelch, gain, sample_rate, output_rate, duration
    ):
        cmd = (
            f"rtl_fm -f {freq} -M fm -s {sample_rate} -r {output_rate} "
            f"-E offset -l {squelch} -g {gain} | "
            f"multimon-ng -t raw -a POCSAG512 -a POCSAG1200 -a POCSAG2400 -f alpha -"
        )

        self._process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        read_task = asyncio.create_task(self._read_output(self._process))

        try:
            await asyncio.wait_for(self._process.wait(), timeout=duration)
        except asyncio.TimeoutError:
            pass
        except Exception:
            pass

        read_task.cancel()
        try:
            await read_task
        except asyncio.CancelledError:
            pass

        # Log stderr si le processus a echoue
        if self._process and self._process.returncode != 0 and self._process.stderr:
            try:
                err = await self._process.stderr.read()
                if err:
                    log.warning("Radio stderr: %s", err.decode("utf-8", errors="replace")[:300])
            except Exception:
                pass

        await self._kill_processes()

    async def _read_output(self, proc):
        try:
            while self._running and proc.stdout and not proc.stdout.at_eof():
                line = await proc.stdout.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").strip()
                if decoded:
                    parsed = parse_line(decoded)
                    if parsed and self.on_message:
                        asyncio.ensure_future(self.on_message(parsed))
        except Exception:
            pass

    async def _kill_processes(self):
        proc = self._process
        if proc and proc.returncode is None:
            try:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=2)
                except asyncio.TimeoutError:
                    proc.kill()
            except Exception:
                pass
        self._process = None