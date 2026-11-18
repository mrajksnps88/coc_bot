"""Bot configuration and settings."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from coc_bot.config.settings import BotSettings


def load_config(path: Path | str) -> dict[str, Any]:
    """Load game configuration from a YAML file."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_settings(**overrides: Any) -> BotSettings:
    """Create a BotSettings instance with optional field overrides."""
    return BotSettings(**overrides)
