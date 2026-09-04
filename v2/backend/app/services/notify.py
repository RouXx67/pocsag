from __future__ import annotations

from datetime import datetime

import requests

from app.services.geocoding import geocode


def send_discord(
    webhook_url: str,
    ric: str,
    ric_display: str,
    func: str,
    message: str,
    address: str,
    is_urgent: bool,
    is_test: bool = False,
) -> tuple[bool, str]:
    if not webhook_url or "http" not in webhook_url:
        return False, "Discord non configur\u00e9"

    title = (
        "Test Webhook Discord - POCSAG"
        if is_test
        else (
            f"ALERTE PRIORITAIRE - {ric_display}"
            if is_urgent
            else f"Alerte POCSAG - {ric_display}"
        )
    )
    color = 5814783 if is_test else (15158332 if is_urgent else 3447003)

    fields = [
        {"name": "RIC / Capcode", "value": ric_display, "inline": True},
        {"name": "Sous-adresse", "value": str(func), "inline": True},
        {"name": "Message", "value": message if message else "*Signal / Sans texte*"},
    ]

    if address:
        encoded = requests.utils.quote(address)
        fields.append(
            {
                "name": "Localisation",
                "value": f"**{address}**\n[Google Maps](https://www.google.com/maps/search/?api=1&query={encoded})",
                "inline": False,
            }
        )

    payload = {
        "content": "@everyone" if is_urgent and not is_test else "",
        "embeds": [
            {
                "title": title,
                "color": color,
                "fields": fields,
                "footer": {"text": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
            }
        ],
    }
    try:
        r = requests.post(webhook_url, json=payload, timeout=5)
        return (True, "OK") if r.status_code in (200, 204) else (False, f"HTTP {r.status_code}")
    except Exception as e:
        return False, str(e)


def send_telegram(
    bot_token: str,
    chat_id: str,
    ric_display: str,
    func: str,
    message: str,
    address: str,
    is_urgent: bool,
    is_test: bool = False,
) -> tuple[bool, str]:
    if not bot_token or not chat_id:
        return False, "Telegram non configur\u00e9"

    header = (
        "TEST TELEGRAM - POCSAG"
        if is_test
        else ("ALERTE PRIORITAIRE POCSAG" if is_urgent else "ALERTE POCSAG")
    )
    text = (
        f"*{header}*\n\n"
        f"*RIC / Engin :* `{ric_display}`\n"
        f"*Sous-adresse :* `{func}`\n"
        f"*Message :* {message if message else '_Signal / Sans texte_'}\n"
    )

    if address:
        encoded = requests.utils.quote(address)
        text += (
            f"\n*Localisation :* {address}\n"
            f"[Google Maps](https://www.google.com/maps/search/?api=1&query={encoded})"
        )

    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            },
            timeout=5,
        )
        if address:
            lat, lon = geocode(address)
            if lat and lon:
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendLocation",
                    json={"chat_id": chat_id, "latitude": lat, "longitude": lon},
                    timeout=5,
                )
        return True, "OK"
    except Exception as e:
        return False, str(e)