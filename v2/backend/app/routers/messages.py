from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Alias, ConfigEntry, Message
from app.schemas import MessageOut

router = APIRouter(tags=["messages"])


@router.get("/api/messages", response_model=list[MessageOut])
async def get_messages(
    limit: int = Query(300, le=1000),
    search: str = Query(""),
    urgent_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Message).order_by(Message.created_at.desc()).limit(limit)

    if search:
        stmt = stmt.where(
            Message.ric.ilike(f"%{search}%")
            | Message.message.ilike(f"%{search}%")
        )

    if urgent_only:
        kw_entry = await db.get(ConfigEntry, "keywords")
        if kw_entry and kw_entry.value:
            keywords = [k.strip() for k in kw_entry.value.split(",") if k.strip()]
            if keywords:
                stmt = stmt.where(
                    or_(*[Message.message.ilike(f"%{kw}%") for kw in keywords])
                )

    rows = await db.execute(stmt)
    messages = rows.scalars().all()

    alias_rows = await db.execute(select(Alias))
    aliases = {a.ric: a.name for a in alias_rows.scalars()}

    kw_entry = await db.get(ConfigEntry, "keywords")
    keywords = []
    if kw_entry and kw_entry.value:
        keywords = [k.strip().lower() for k in kw_entry.value.split(",") if k.strip()]

    result = []
    for m in messages:
        is_urgent = any(kw in m.message.lower() for kw in keywords) if keywords else False
        result.append(
            MessageOut(
                id=m.id,
                ric=m.ric,
                func=m.func,
                message=m.message,
                alias=aliases.get(m.ric, ""),
                address=m.address,
                lat=m.lat,
                lon=m.lon,
                is_urgent=is_urgent,
                created_at=m.created_at,
            )
        )

    return result


@router.post("/api/clear-logs")
async def clear_logs(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import delete as sa_delete
    await db.execute(sa_delete(Message))
    await db.commit()
    return {"status": "ok"}