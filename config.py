from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = "config.yaml"


def load_config(path: str | None = None) -> dict[str, Any]:
    config_path = path or os.environ.get("BOT_CONFIG_PATH", DEFAULT_CONFIG_PATH)
    resolved = Path(config_path)
    with resolved.open("r", encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    if not isinstance(cfg, dict):
        raise ValueError("config.yaml must be a mapping at top level")
    return cfg
