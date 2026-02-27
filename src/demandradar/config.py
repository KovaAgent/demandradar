from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR_NAME = ".demandradar"
CONFIG_FILE_NAME = "config.yaml"

DEFAULT_CONFIG: dict[str, Any] = {
    "openai_api_key": "",
    "github_token": "",
    "sources": ["hn", "github", "reddit"],
    "lookback_days": 30,
    "max_signals_per_source": 200,
}


def get_config_dir(home: str | Path | None = None) -> Path:
    base = Path(home) if home is not None else Path.home()
    return base / CONFIG_DIR_NAME


def get_config_path(home: str | Path | None = None) -> Path:
    return get_config_dir(home=home) / CONFIG_FILE_NAME


def ensure_config_file(home: str | Path | None = None) -> Path:
    path = get_config_path(home=home)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(DEFAULT_CONFIG, sort_keys=False), encoding="utf-8")
    return path


def load_config(home: str | Path | None = None) -> dict[str, Any]:
    path = ensure_config_file(home=home)
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    config = deepcopy(DEFAULT_CONFIG)
    if isinstance(loaded, dict):
        config.update(loaded)
    config["openai_api_key"] = os.getenv("OPENAI_API_KEY", config.get("openai_api_key", ""))
    config["github_token"] = os.getenv("GITHUB_TOKEN", config.get("github_token", ""))
    config["sources"] = [str(s).strip() for s in config.get("sources", []) if str(s).strip()]
    if not config["sources"]:
        config["sources"] = DEFAULT_CONFIG["sources"][:]
    config["lookback_days"] = int(config.get("lookback_days", DEFAULT_CONFIG["lookback_days"]))
    config["max_signals_per_source"] = int(
        config.get("max_signals_per_source", DEFAULT_CONFIG["max_signals_per_source"])
    )
    return config


def resolve_sources(sources_arg: str | None, config_sources: list[str]) -> list[str]:
    if not sources_arg:
        return config_sources
    return [s.strip().lower() for s in sources_arg.split(",") if s.strip()]
