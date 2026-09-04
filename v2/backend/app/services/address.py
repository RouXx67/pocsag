from __future__ import annotations

import re

PREFIXES = [
    "AVP", "SAP", "FEU", "SECOURS", "INTERVENTION",
    "VL CONTRE ARBRE", "PL CONTRE ARBRE",
    "DEGAGEMENT", "RECONNAISSANCE",
]

ENGIN_RE = re.compile(r"\b[A-Z]{3,}\d{3}(?:\.[A-Z0-9]+)?\s*")

CITY_FIRST_RE = re.compile(
    r"^([A-ZÀ-ÖØ-Þ\s\-]{3,})\s+"
    r"(\d+[\w\s\-\.]+\s+(?:RUE|AVENUE|BOULEVARD|IMPASSE|CHEMIN|"
    r"ROUTE|PLACE|ALLÉE|ALLEE|QUAI|CRS|CR|RES|RESIDENCE)\b.*)$",
    re.IGNORECASE,
)


def extract_address(message: str) -> str:
    """Extract a human-readable address from a POCSAG message."""
    if not message:
        return ""

    cleaned = message
    for prefix in PREFIXES:
        if cleaned.upper().startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()

    cleaned = ENGIN_RE.sub("", cleaned).strip()

    m = CITY_FIRST_RE.match(cleaned)
    if m:
        city = m.group(1).strip()
        street = m.group(2).strip()
        return f"{street}, {city}"

    parts = cleaned.split("/")
    if len(parts) >= 2:
        return " ".join(p.strip() for p in parts[1:]).strip()

    return cleaned