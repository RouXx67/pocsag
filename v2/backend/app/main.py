from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import async_session_factory, engine, get_db
from app.models import Base, ConfigEntry, Message
from app.routers import config as config_router
from app.routers import messages as messages_router
from app.routers import service as service_router
from app.routers import stats as stats_router
from app.services.address import extract_address
from app.services.geocoding import geocode
from app.services.notify import send_discord, send_telegram
from app.services.radio import RadioScanner

log = logging.getLogger("pocsag")

radio_scanner: RadioScanner | None = None


async def _on_message(parsed: dict):
    """Callback when a POCSAG line is parsed."""
    try:
        async with async_session_factory() as db:
            from app.models import Alias, BlacklistEntry, ConfigEntry, Message
            from sqlalchemy import select

            ric = parsed["ric"]
            func = parsed["func"]
            message = parsed["message"]

            bl = await db.get(BlacklistEntry, ric)
            if bl:
                return

            cfg_notify = await db.get(ConfigEntry, "notify_empty")
            notify_empty = cfg_notify.value.lower() == "true" if cfg_notify else True
            if not message and not notify_empty:
                return

            kw_entry = await db.get(ConfigEntry, "keywords")
            keywords = []
            if kw_entry and kw_entry.value:
                keywords = [k.strip().lower() for k in kw_entry.value.split(",") if k.strip()]
            is_urgent = any(kw in message.lower() for kw in keywords) if message and keywords else False

            alias_row = await db.get(Alias, ric)
            alias_name = alias_row.name if alias_row else ""
            ric_display = f"{ric} ({alias_name})" if alias_name else ric

            addr = extract_address(message) if message else ""

            lat, lon = None, None
            if addr:
                lat, lon = geocode(addr)

            db.add(Message(
                ric=ric,
                func=func,
                message=message if message else "Signal / Sans texte",
                address=addr,
                lat=lat,
                lon=lon,
                is_urgent=is_urgent,
                raw_line=parsed.get("raw_line", ""),
            ))
            await db.commit()

            # Notifications in background
            wh = await db.get(ConfigEntry, "discord_webhook")
            tg_token = await db.get(ConfigEntry, "telegram_bot_token")
            tg_chat = await db.get(ConfigEntry, "telegram_chat_id")

            if wh and wh.value:
                send_discord(wh.value, ric, ric_display, func, message, addr, is_urgent)
            if tg_token and tg_token.value and tg_chat and tg_chat.value:
                send_telegram(tg_token.value, tg_chat.value, ric_display, func, message, addr, is_urgent)

    except Exception as e:
        log.error("on_message error: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global radio_scanner

    log.info("Starting POCSAG Monitor v2")
    os.makedirs(settings.data_dir, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        for key, default in [
            ("admin_password_hash", None),
            ("frequencies", ",".join(settings.default_frequencies)),
            ("keywords", ",".join(settings.default_keywords)),
            ("notify_empty", "true"),
            ("scan_interval", str(settings.default_scan_interval)),
            ("squelch", "0"),
            ("gain", "19.2"),
            ("sample_rate", "176400"),
            ("output_rate", "22050"),
        ]:
            existing = await db.get(ConfigEntry, key)
            if not existing:
                if key == "admin_password_hash":
                    from app.auth import hash_password
                    db.add(ConfigEntry(key=key, value=hash_password(settings.admin_password_default)))
                else:
                    db.add(ConfigEntry(key=key, value=default))
        await db.commit()

    radio_scanner = RadioScanner(on_message=_on_message)
    asyncio.create_task(radio_scanner.start())

    yield

    if radio_scanner:
        await radio_scanner.stop()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(config_router.router)
app.include_router(messages_router.router)
app.include_router(service_router.router)
app.include_router(stats_router.router)


# Serve static frontend
frontend_dir = Path(__file__).parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)