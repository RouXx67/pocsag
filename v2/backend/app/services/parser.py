from __future__ import annotations

import re

POCSAG_RE = re.compile(
    r"POCSAG\d+:\s+Address:\s+(\d+)\s+Function:\s+(\d+)(?:\s+Alpha:\s+(.*))?"
)


def parse_line(line: str) -> dict | None:
    """Parse a single POCSAG line from multimon-ng output."""
    if not line:
        return None
    match = POCSAG_RE.search(line)
    if not match:
        return None
    ric, func, text = match.groups()
    return {
        "ric": ric,
        "func": func,
        "message": text.strip() if text else "",
        "raw_line": line.strip(),
    }