from __future__ import annotations

import subprocess

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.models import ConfigEntry
from app.schemas import DongleStatus, ServiceStatus
from app.config import settings
from app.services.radio import CURRENT_SCAN_FREQ, check_dongle, MULTIMON_LOG, _log_buffer_lock

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
        current_freq=CURRENT_SCAN_FREQ or (freqs[0] if freqs else None),
    )


@router.get("/api/radio/dongle", response_model=DongleStatus)
async def radio_dongle():
    ok, msg = check_dongle()
    return DongleStatus(
        detected=ok,
        message=msg,
        current_freq=CURRENT_SCAN_FREQ,
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


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Convertit une chaîne de version 'X.Y.Z' en tuple d'entiers.
    Gère les numéros, supprime les espaces, supprime un préfixe 'v'.
    Retourne un tuple vide si la version n'est pas parseable."""
    if not version_str:
        return ()
    # Supprime 'v' devant, et éventuel suffixe après '-'
    clean = version_str.lstrip('v').strip()
    # Ignore tout ce qui suit un tiret (par ex. 2.4.0-alpha)
    dash_idx = clean.find('-')
    if dash_idx >= 0:
        clean = clean[:dash_idx]
    parts = clean.split('.')
    parsed = []
    for p in parts:
        try:
            parsed.append(int(p))
        except ValueError:
            # Si un segment n'est pas un entier, on s'arrête là
            break
    return tuple(parsed)


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
        remote_raw = r.text.strip() if r.status_code == 200 else ""
        remote_parsed = _parse_version(remote_raw)
        local_parsed = _parse_version(settings.version)
        
        # Une mise à jour est disponible seulement si la version distante est
        # sémantiquement supérieure à la locale, et si les deux sont parseables.
        available = bool(remote_parsed and local_parsed and remote_parsed > local_parsed)
        return {"update_available": available, "local": settings.version, "remote": remote_raw}
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

    # Detacher l'update du process du service (sinon systemctl stop le tue)
    # nohup + setsid pour survivre a la mort du process parent
    log_path = "/var/log/pocsag-update.log"
    try:
        sp.Popen(
            f"nohup setsid bash {script} --force > {log_path} 2>&1 < /dev/null &",
            shell=True,
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
            start_new_session=True,
        )
        return {"status": "updating"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/api/multimon-logs")
async def get_multimon_logs(lines: int = 200):
    """
    Renvoie les N dernières lignes du buffer de logs multimon-ng/rtl_fm.
    """
    from app.services.radio import MULTIMON_LOG, _log_buffer_lock
    with _log_buffer_lock:
        recent = list(MULTIMON_LOG)[-lines:] if lines > 0 else []
    return {
        "lines": recent,
        "count": len(recent),
        "buffer_size": len(MULTIMON_LOG),
    }