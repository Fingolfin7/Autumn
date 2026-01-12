"""Configuration management for Autumn CLI."""

import os
import yaml
from pathlib import Path
from typing import Optional, Any


CONFIG_DIR = Path.home() / ".autumn"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


DEFAULT_GREETING_ACTIVITY_WEIGHT = 0.35
DEFAULT_GREETING_MOON_CAMEO_WEIGHT = 0.15


def ensure_config_dir():
    """Create config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Load configuration from file."""
    ensure_config_dir()
    
    if not CONFIG_FILE.exists():
        return {}
    
    try:
        with open(CONFIG_FILE, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def save_config(config: dict):
    """Save configuration to file."""
    ensure_config_dir()
    
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def get_api_key() -> Optional[str]:
    """Get API key from config or environment variable."""
    # Environment variable takes precedence
    env_key = os.getenv("AUTUMN_API_KEY")
    if env_key:
        return env_key
    
    # Fall back to config file
    config = load_config()
    return config.get("api_key")


def get_base_url() -> str:
    """Get base URL from config or environment variable, with default."""
    # Environment variable takes precedence
    env_url = os.getenv("AUTUMN_API_BASE")
    if env_url:
        return env_url.rstrip("/")
    
    # Fall back to config file
    config = load_config()
    return config.get("base_url", "http://localhost:8000").rstrip("/")


def set_api_key(api_key: str):
    """Set API key in config file."""
    config = load_config()
    config["api_key"] = api_key
    save_config(config)


def set_base_url(base_url: str):
    """Set base URL in config file."""
    config = load_config()
    config["base_url"] = base_url.rstrip("/")
    save_config(config)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def get_greeting_activity_weight() -> float:
    """How often greetings prefer activity-based lines (0.0-1.0)."""
    config = load_config()
    try:
        return _clamp01(config.get("greeting_activity_weight", DEFAULT_GREETING_ACTIVITY_WEIGHT))
    except Exception:
        return DEFAULT_GREETING_ACTIVITY_WEIGHT


def set_greeting_activity_weight(value: float) -> float:
    config = load_config()
    v = _clamp01(value)
    config["greeting_activity_weight"] = v
    save_config(config)
    return v


def get_greeting_moon_cameo_weight() -> float:
    """How often non-full/new moon phases can appear as a cameo (0.0-1.0)."""
    config = load_config()
    try:
        return _clamp01(config.get("greeting_moon_cameo_weight", DEFAULT_GREETING_MOON_CAMEO_WEIGHT))
    except Exception:
        return DEFAULT_GREETING_MOON_CAMEO_WEIGHT


def set_greeting_moon_cameo_weight(value: float) -> float:
    config = load_config()
    v = _clamp01(value)
    config["greeting_moon_cameo_weight"] = v
    save_config(config)
    return v


def get_config_value(key: str, default: Any = None) -> Any:
    """Get a config value by dotted path, e.g. 'meta_cache.fetched_at'.

    Returns default if key is missing.
    """
    cfg = load_config() or {}
    cur: Any = cfg
    for part in str(key).split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def set_config_value(key: str, value: Any) -> None:
    """Set a config value by dotted path, creating intermediate dicts."""
    cfg = load_config() or {}
    parts = str(key).split(".")
    cur: Any = cfg
    for part in parts[:-1]:
        if part not in cur or not isinstance(cur.get(part), dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value
    save_config(cfg)
