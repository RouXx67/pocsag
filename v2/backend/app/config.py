from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "POCSAG Monitor v2"
    version: str = "2.1.1"

    host: str = "127.0.0.1"
    port: int = 8080

    db_url: str = "sqlite+aiosqlite:////opt/pocsag/v2/data/pocsag.db"

    base_dir: Path = Path(os.path.dirname(os.path.abspath(__file__)))
    data_dir: Path = base_dir / ".." / "data"

    log_file: str = ""
    log_level: str = "INFO"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    admin_password_default: str = "admin"

    default_frequencies: list[str] = ["85.955M", "173512.5k"]
    max_frequencies: int = 3
    scan_interval_min: int = 5
    default_scan_interval: int = 30

    default_keywords: list[str] = [
        "AVP", "FEU", "DESINCARCERATION", "RENFORT", "URGENT"
    ]

    geo_timeout: int = 3
    log_max_entries: int = 300

    model_config = {"env_prefix": "POCSAG_"}

    @property
    def db_path(self) -> Path:
        if self.db_url.startswith("sqlite"):
            path = self.db_url.replace("sqlite+aiosqlite:///", "")
            return Path(path)
        return Path("/opt/pocsag/v2/data/pocsag.db")


settings = Settings()