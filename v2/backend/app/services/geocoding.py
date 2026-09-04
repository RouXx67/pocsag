from __future__ import annotations

from typing import Optional

import requests

from app.config import settings


def geocode(address: str) -> tuple[Optional[float], Optional[float]]:
    """Geocode an address using the French BAN API."""
    if not address:
        return None, None
    try:
        url = (
            f"https://api-adresse.data.gouv.fr/search/"
            f"?q={requests.utils.quote(address)}&limit=1"
        )
        r = requests.get(url, timeout=settings.geo_timeout)
        if r.status_code == 200:
            data = r.json()
            if data.get("features"):
                coords = data["features"][0]["geometry"]["coordinates"]
                return coords[1], coords[0]
    except Exception:
        pass
    return None, None