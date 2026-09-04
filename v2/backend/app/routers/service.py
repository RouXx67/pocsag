from __future__ import annotations

import asyncio
import subprocess

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ConfigEntry
from app.schemas import ServiceStatus
from app.config import settings

router = APIRouter(tags=["service"])


@router.get("/api/service/status", response_model=ServiceStatus)
async def service_status(db: AsyncSession = Depends(get_db)):
    try:
        r = subprocess.run(
            ["systemctl", "is-active", "pocsag"],
            capture_output=True, text=True, timeout=3,
        )
        active = r.stdout.strip() == "active"
    except Exception:
        active = False

    freqs_str = ""
    row = await db.get(ConfigEntry, "frequencies")
    if row and row.value:
        freqs_str = row.value
    freqs = (
        [f.strip() for f in freqs_str.split(",") if f.strip()]
        if freqs_str
        else settings.default_frequencies
    )

    return ServiceStatus(
        active=active,
        frequencies=freqs,
        current_freq=freqs[0] if freqs else None,
    )


@router.post("/api/service/restart")
async def service_restart():
    try:
        subprocess.run(["systemctl", "restart", "pocsag"], timeout=10)
        return {"status": "restarting"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/api/logs")
async def get_logs():
    try:
        r = subprocess.run(
            ["journalctl", "-u", "pocsag", "-n", "200", "--no-pager", "--output=short-iso"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout or "(vide)"
    except Exception as e:
        return f"Erreur: {e}"


@router.post("/api/test-discord")
async def test_discord():
    from app.services.notify import send_discord
    from app.database import async_session_factory
    from app.models import ConfigEntry

    async with async_session_factory() as db:
        wh = await db.get(ConfigEntry, "discord_webhook")
        url = wh.value if wh else ""

    if not url:
        return {"success": False, "message": "Webhook non configur\u00e9"}

    ok, msg = send_discord(
        url, "1234567", "1234567 (TEST)", "1",
        "SAP VERT A DOMICILE VSAV001.COND BENFELD 7C RUE PETIT REMPART",
        "BENFELD 7C RUE PETIT REMPART",
        is_urgent=False, is_test=True,
    )
    return {"success": ok, "message": msg}


@router.get("/api/update/check")
async def check_update():
    try:
        import requests
        r = requests.get(
            "https://raw.githubusercontent.com/RouXx67/pocsag/main/VERSION",
            timeout=3,
        )
        if r.status_code != 200:
            r = requests.get(
                "https://raw.githubusercontent.com/RouXx67/pocsag/master/VERSION",
                timeout=3,
            )
        remote = r.text.strip() if r.status_code == 200 else settings.version
        available = settings.version != remote and len(remote) > 0
        return {"update_available": available, "local": settings.version, "remote": remote}
    except Exception as e:
        return {"update_available": False, "error": str(e)}


@router.post("/api/update/run")
async def run_update():
    import os
    import subprocess as sp

    candidates = [
        "/opt/pocsag/v2/scripts/update.sh",
        "/opt/pocsag/update.sh",
        "/home/pocsag/pocsag/v2/scripts/update.sh",
    ]
    script = None
    for c in candidates:
        if os.path.exists(c):
            script = c
            break

    if not script:
        return {"status": "error", "message": "Script update.sh introuvable"}

    def _run():
        sp.run(["bash", script, "--force"], timeout=60)

    import threading
    threading.Thread(target=_run, daemon=True).start()
    return {"status": "updating"}