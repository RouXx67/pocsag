from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MessageOut(BaseModel):
    id: int
    ric: str
    func: str
    message: str
    alias: str = ""
    address: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    is_urgent: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    ric: str
    func: str
    message: str = ""
    raw_line: Optional[str] = None


class AliasOut(BaseModel):
    ric: str
    name: str


class AliasCreate(BaseModel):
    ric: str
    name: str


class BlacklistOut(BaseModel):
    ric: str


class BlacklistCreate(BaseModel):
    ric: str


class ConfigOut(BaseModel):
    discord_webhook: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    notify_empty: bool = True
    aliases: dict[str, str] = {}
    blacklist: list[str] = []
    keywords: list[str] = Field(default_factory=lambda: [
        "AVP", "FEU", "DESINCARCERATION", "RENFORT", "URGENT"
    ])
    frequencies: list[str] = Field(default_factory=lambda: ["85.955M", "173512.5k"])
    scan_interval: int = 30
    squelch: int = 0
    gain: str = "19.2"
    sample_rate: str = "176400"
    output_rate: str = "22050"


class ConfigUpdate(BaseModel):
    discord_webhook: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    notify_empty: Optional[bool] = None
    keywords: Optional[list[str]] = None
    frequencies: Optional[list[str]] = None
    scan_interval: Optional[int] = None
    squelch: Optional[int] = None
    gain: Optional[str] = None
    sample_rate: Optional[str] = None
    output_rate: Optional[str] = None


class LoginRequest(BaseModel):
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ServiceStatus(BaseModel):
    active: bool
    frequencies: list[str]
    current_freq: Optional[str] = None


class VersionOut(BaseModel):
    version: str


class DongleStatus(BaseModel):
    detected: bool
    message: str
    current_freq: Optional[str] = None


class StatsOut(BaseModel):
    total_today: int = 0
    urgent_today: int = 0
    last_activity: Optional[str] = None
    top_ric: Optional[str] = None
    top_ric_alias: str = ""