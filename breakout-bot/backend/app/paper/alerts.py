"""Alertes optionnelles (PRD §8.7) : Telegram et/ou webhook générique.

No-op si non configurées (variables d'environnement TELEGRAM_BOT_TOKEN /
TELEGRAM_CHAT_ID / ALERT_WEBHOOK_URL absentes).
"""

from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger(__name__)


def send_alert(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    webhook = os.environ.get("ALERT_WEBHOOK_URL")
    try:
        if token and chat_id:
            httpx.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message},
                timeout=10.0,
            )
        if webhook:
            httpx.post(webhook, json={"text": message}, timeout=10.0)
    except Exception as exc:
        log.warning("envoi d'alerte échoué : %s", exc)
