from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_token, hash_password, create_token, verify_password
from app.config import settings
from app.database import get_db
from app.models import Alias, BlacklistEntry, ConfigEntry
from app.schemas import (
    AliasCreate, AliasOut, BlacklistCreate, BlacklistOut,
    ConfigOut, ConfigUpdate, LoginRequest, TokenOut, VersionOut,
)

router = APIRouter(tags=["config"])


async def _require_auth(token: str = Query(""), db: AsyncSession = Depends(get_db)):
    entry = await db.get(ConfigEntry, "admin_password_hash")
    pwd_hash = entry.value if entry else hash_password(settings.admin_password_default)
    if not verify_token(token, pwd_hash):
        raise HTTPException(status_code=401, detail="Non autoris\u00e9")


async def _get_config_value(db: AsyncSession, key: str, default: str = "") -> str:
    entry = await db.get(ConfigEntry, key)
    return entry.value if entry else default


async def _set_config_value(db: AsyncSession, key: str, value: str):
    entry = await db.get(ConfigEntry, key)
    if entry:
        entry.value = str(value)
    else:
        db.add(ConfigEntry(key=key, value=str(value)))
    await db.commit()


@router.get("/api/version", response_model=VersionOut)
async def get_version():
    return VersionOut(version=settings.version)


@router.get("/api/config", response_model=ConfigOut)
async def get_config(db: AsyncSession = Depends(get_db)):
    cfg = ConfigOut()
    rows = await db.execute(select(ConfigEntry))
    for row in rows.scalars():
        if row.key == "discord_webhook":
            cfg.discord_webhook = row.value
        elif row.key == "telegram_bot_token":
            cfg.telegram_bot_token = row.value
        elif row.key == "telegram_chat_id":
            cfg.telegram_chat_id = row.value
        elif row.key == "notify_empty":
            cfg.notify_empty = row.value.lower() == "true"
        elif row.key == "keywords":
            cfg.keywords = [k.strip() for k in row.value.split(",") if k.strip()]
        elif row.key == "frequencies":
            cfg.frequencies = [f.strip() for f in row.value.split(",") if f.strip()]
        elif row.key == "scan_interval":
            try:
                cfg.scan_interval = int(row.value)
            except ValueError:
                pass
        elif row.key == "squelch":
            try:
                cfg.squelch = int(row.value)
            except ValueError:
                pass
        elif row.key == "gain":
            cfg.gain = row.value
        elif row.key == "sample_rate":
            cfg.sample_rate = row.value
        elif row.key == "output_rate":
            cfg.output_rate = row.value

    alias_rows = await db.execute(select(Alias))
    cfg.aliases = {a.ric: a.name for a in alias_rows.scalars()}

    bl_rows = await db.execute(select(BlacklistEntry))
    cfg.blacklist = [b.ric for b in bl_rows.scalars()]

    return cfg


@router.post("/api/config")
async def update_config(
    body: ConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(_require_auth),
):
    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        if key == "keywords" and isinstance(value, list):
            await _set_config_value(db, key, ",".join(value))
        elif key == "frequencies" and isinstance(value, list):
            cleaned = []
            for f in value:
                f = f.strip()
                if f:
                    cleaned.append(f)
                if len(cleaned) >= settings.max_frequencies:
                    break
            if cleaned:
                await _set_config_value(db, key, ",".join(cleaned))
        elif isinstance(value, bool):
            await _set_config_value(db, key, "true" if value else "false")
        else:
            await _set_config_value(db, key, str(value))
    return {"status": "ok"}


@router.post("/api/auth/login", response_model=TokenOut)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    entry = await db.get(ConfigEntry, "admin_password_hash")
    stored_hash = (
        entry.value if entry else hash_password(settings.admin_password_default)
    )
    if not verify_password(body.password, stored_hash):
        raise HTTPException(status_code=401, detail="Mot de passe incorrect")
    token = create_token(stored_hash)
    return TokenOut(access_token=token)


@router.post("/api/auth/change-password")
async def change_password(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    token: str = Query(""),
):
    entry = await db.get(ConfigEntry, "admin_password_hash")
    old_hash = entry.value if entry else hash_password(settings.admin_password_default)
    if not verify_token(token, old_hash):
        raise HTTPException(status_code=401, detail="Non autoris\u00e9")
    await _set_config_value(db, "admin_password_hash", hash_password(body.password))
    return {"status": "ok"}


@router.get("/api/aliases", response_model=list[AliasOut])
async def list_aliases(db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(Alias))
    return [AliasOut(ric=a.ric, name=a.name) for a in rows.scalars()]


@router.post("/api/aliases")
async def create_alias(
    body: AliasCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(_require_auth),
):
    existing = (
        await db.execute(select(Alias).where(Alias.ric == body.ric))
    ).scalar_one_or_none()
    if existing:
        existing.name = body.name
    else:
        db.add(Alias(ric=body.ric, name=body.name))
    await db.commit()
    return {"status": "ok"}


@router.delete("/api/aliases/{ric}")
async def delete_alias(
    ric: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(_require_auth),
):
    await db.execute(delete(Alias).where(Alias.ric == ric))
    await db.commit()
    return {"status": "ok"}


@router.get("/api/blacklist", response_model=list[BlacklistOut])
async def list_blacklist(db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(BlacklistEntry))
    return [BlacklistOut(ric=b.ric) for b in rows.scalars()]


@router.post("/api/blacklist")
async def add_blacklist(
    body: BlacklistCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(_require_auth),
):
    existing = (
        await db.execute(select(BlacklistEntry).where(BlacklistEntry.ric == body.ric))
    ).scalar_one_or_none()
    if not existing:
        db.add(BlacklistEntry(ric=body.ric))
        await db.commit()
    return {"status": "ok"}


@router.delete("/api/blacklist/{ric}")
async def remove_blacklist(
    ric: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(_require_auth),
):
    await db.execute(delete(BlacklistEntry).where(BlacklistEntry.ric == ric))
    await db.commit()
    return {"status": "ok"}