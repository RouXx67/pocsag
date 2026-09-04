from __future__ import annotations

import asyncio
import logging
import os
import signal
from typing import Optional

from app.config import settings
from app.services.parser import parse_line

log = logging.getLogger("pocsag.radio")


class RadioScanner:
    def __init__(self, on_message):
        self._process: Optional[asyncio.subprocess.Process] = None
        self._rtl_process: Optional[asyncio.subprocess.Process] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.on_message = on_message

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self):
        if self._running:
            return
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
                from app.database import async_session_factory
                from app.models import ConfigEntry
                async with async_session_factory() as session:
                    freqs_str = ""
                    scan_interval = settings.default_scan_interval
                    squelch = 0
                    gain = "19.2"
                    sample_rate = "176400"
                    output_rate = "22050"

                    rows = await session.execute(
                        __import__("sqlalchemy").select(ConfigEntry).where(
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

        preexec = getattr(os, "setsid", None)

        try:
            self._rtl_process = await asyncio.create_subprocess_exec(
                *rtl_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                preexec_fn=preexec,
            )
            self._process = await asyncio.create_subprocess_exec(
                *mm_args,
                stdin=self._rtl_process.stdout,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                preexec_fn=preexec,
            )
            if self._rtl_process.stdout:
                self._rtl_process.stdout.close()
        except Exception as e:
            log.error("Failed to start subprocess: %s", e)
            return

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
        for proc_attr in ("_process", "_rtl_process"):
            proc = getattr(self, proc_attr, None)
            if proc and proc.returncode is None:
                try:
                    if hasattr(os, "killpg"):
                        try:
                            pgid = os.getpgid(proc.pid)
                            os.killpg(pgid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                    else:
                        proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=2)
                    except asyncio.TimeoutError:
                        if hasattr(os, "killpg"):
                            try:
                                pgid = os.getpgid(proc.pid)
                                os.killpg(pgid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                        else:
                            proc.kill()
                except Exception:
                    pass
            setattr(self, proc_attr, None)