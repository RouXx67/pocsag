from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Alias, ConfigEntry, Message
from app.schemas import StatsOut

router = APIRouter(tags=["stats"])


@router.get("/api/stats", response_model=StatsOut)
async def get_stats(db: AsyncSession = Depends(get_db)):
    today = date.today()
    stmt = select(func.count(Message.id)).where(
        func.date(Message.created_at) == today
    )
    total = (await db.execute(stmt)).scalar() or 0

    urgent_kw = await db.get(ConfigEntry, "keywords")
    keywords = []
    if urgent_kw and urgent_kw.value:
        keywords = [k.strip().lower() for k in urgent_kw.value.split(",") if k.strip()]

    urgent = 0
    if keywords:
        conditions = [Message.message.ilike(f"%{kw}%") for kw in keywords]
        urgent_stmt = (
            select(func.count(Message.id))
            .where(func.date(Message.created_at) == today)
            .where(or_(*conditions))
        )
        urgent = (await db.execute(urgent_stmt)).scalar() or 0

    last = (
        await db.execute(
            select(Message)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    top_ric_row = (
        await db.execute(
            select(Message.ric, func.count(Message.id).label("cnt"))
            .where(func.date(Message.created_at) == today)
            .group_by(Message.ric)
            .order_by(func.count(Message.id).desc())
            .limit(1)
        )
    ).first()

    top_ric = None
    top_alias = ""
    if top_ric_row:
        top_ric = top_ric_row[0]
        alias_entry = await db.get(Alias, top_ric)
        if alias_entry:
            top_alias = alias_entry.name

    now = datetime.utcnow()
    hourly_raw = await db.execute(
        select(
            func.strftime("%Y-%m-%d %H", Message.created_at).label("hour"),
            func.count(Message.id).label("cnt"),
        )
        .where(Message.created_at >= now - timedelta(hours=24))
        .group_by("hour")
        .order_by("hour")
    )
    hourly_map = {row[0]: row[1] for row in hourly_raw}
    hourly = []
    for i in range(24, 0, -1):
        h = (now - timedelta(hours=i)).strftime("%Y-%m-%d %H")
        hourly.append(hourly_map.get(h, 0))
    h = now.strftime("%Y-%m-%d %H")
    hourly.append(hourly_map.get(h, 0))

    return StatsOut(
        total_today=total,
        urgent_today=urgent,
        last_activity=last.created_at.isoformat() if last else None,
        top_ric=top_ric,
        top_ric_alias=top_alias,
        hourly=hourly,
    )