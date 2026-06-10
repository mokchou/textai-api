"""Hachage canonique d'une configuration : entre dans le run_id (reproductibilité)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.config.models import BotConfig


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def config_hash(config: BotConfig) -> str:
    payload = canonical_json(config.model_dump(mode="json"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
