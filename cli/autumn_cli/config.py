"""Configuration management for Autumn CLI."""

import os
import yaml
from pathlib import Path
from typing import Optional, Any


CONFIG_DIR = Path.home() / ".autumn"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


DEFAULT_GREETING_GENERAL_WEIGHT = 0.4
DEFAULT_GREETING_ACTIVITY_WEIGHT = 0.4
DEFAULT_GREETING_MOON_CAMEO_WEIGHT = 0.2


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
            data = yaml.safe_load(f) or {}
            # If config is corrupted (e.g. YAML root is a list), repair by resetting.
            if not isinstance(data, dict):
                return {}
            return data
    except (OSError, yaml.YAMLError):
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


def _normalize_greeting_weights(
    *,
    general: float,
    activity: float,
    moon_cameo: float,
) -> tuple[float, float, float, bool]:
    """Clamp weights to keep the total ≤ 1.0.

    Clamps each weight to 0..1 first, then if the total exceeds 1, reduces the other
    weights (not the one you just set) proportionally.

    Returns (general, activity, moon_cameo, changed).
    """

    g = _clamp01(general)
    a = _clamp01(activity)
    m = _clamp01(moon_cameo)

    total = g + a + m
    if total <= 1.0:
        return g, a, m, (g != general or a != activity or m != moon_cameo)

    return g, a, m, True


def set_greeting_weights(
    *,
    general: float | None = None,
    activity: float | None = None,
    moon_cameo: float | None = None,
) -> dict:
    """Set greeting weights, clamping to keep total ≤ 1.0.

    The most recently provided value is kept as-is (after 0..1 clamp). The other
    weights are proportionally reduced if needed.

    Returns the final weights written to config.
    """

    config = load_config()

    g = float(config.get("greeting_general_weight", DEFAULT_GREETING_GENERAL_WEIGHT))
    a = float(config.get("greeting_activity_weight", DEFAULT_GREETING_ACTIVITY_WEIGHT))
    m = float(config.get("greeting_moon_cameo_weight", DEFAULT_GREETING_MOON_CAMEO_WEIGHT))

    last_key: str | None = None
    if general is not None:
        g = general
        last_key = "general"
    if activity is not None:
        a = activity
        last_key = "activity"
    if moon_cameo is not None:
        m = moon_cameo
        last_key = "moon"

    # Clamp individual inputs
    g = _clamp01(g)
    a = _clamp01(a)
    m = _clamp01(m)

    total = g + a + m
    if total > 1.0 and last_key is not None:
        if last_key == "general":
            fixed = g
            other_a, other_m = a, m
            other_total = other_a + other_m
            remaining = max(0.0, 1.0 - fixed)
            if other_total > 0:
                scale = remaining / other_total
                a = other_a * scale
                m = other_m * scale
            else:
                a = 0.0
                m = 0.0
        elif last_key == "activity":
            fixed = a
            other_g, other_m = g, m
            other_total = other_g + other_m
            remaining = max(0.0, 1.0 - fixed)
            if other_total > 0:
                scale = remaining / other_total
                g = other_g * scale
                m = other_m * scale
            else:
                g = 0.0
                m = 0.0
        else:  # moon
            fixed = m
            other_g, other_a = g, a
            other_total = other_g + other_a
            remaining = max(0.0, 1.0 - fixed)
            if other_total > 0:
                scale = remaining / other_total
                g = other_g * scale
                a = other_a * scale
            else:
                g = 0.0
                a = 0.0

    # Final safety clamp (float ops may drift)
    g, a, m, _ = _normalize_greeting_weights(general=g, activity=a, moon_cameo=m)

    config["greeting_general_weight"] = g
    config["greeting_activity_weight"] = a
    config["greeting_moon_cameo_weight"] = m
    save_config(config)

    return {
        "greeting_general_weight": g,
        "greeting_activity_weight": a,
        "greeting_moon_cameo_weight": m,
    }


def get_greeting_general_weight() -> float:
    """How often greetings prefer general (non-activity, non-moon) lines (0.0-1.0)."""
    config = load_config()
    try:
        return _clamp01(config.get("greeting_general_weight", DEFAULT_GREETING_GENERAL_WEIGHT))
    except (ValueError, TypeError):
        return DEFAULT_GREETING_GENERAL_WEIGHT


def set_greeting_general_weight(value: float) -> float:
    return float(set_greeting_weights(general=value)["greeting_general_weight"])


def get_greeting_activity_weight() -> float:
    """How often greetings prefer activity-based lines (0.0-1.0)."""
    config = load_config()
    try:
        return _clamp01(config.get("greeting_activity_weight", DEFAULT_GREETING_ACTIVITY_WEIGHT))
    except (ValueError, TypeError):
        return DEFAULT_GREETING_ACTIVITY_WEIGHT


def set_greeting_activity_weight(value: float) -> float:
    return float(set_greeting_weights(activity=value)["greeting_activity_weight"])


def get_greeting_moon_cameo_weight() -> float:
    """How often non-full/new moon phases can appear as a cameo (0.0-1.0)."""
    config = load_config()
    try:
        return _clamp01(config.get("greeting_moon_cameo_weight", DEFAULT_GREETING_MOON_CAMEO_WEIGHT))
    except (ValueError, TypeError):
        return DEFAULT_GREETING_MOON_CAMEO_WEIGHT


def set_greeting_moon_cameo_weight(value: float) -> float:
    return float(set_greeting_weights(moon_cameo=value)["greeting_moon_cameo_weight"])


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


def get_insecure() -> bool:
    """Whether to disable TLS certificate verification for API calls.

    Controlled by either:
      - env var AUTUMN_INSECURE=1/true/yes/on
      - config.yaml key `tls.insecure: true` (preferred)
      - config.yaml key `insecure: true` (legacy)

    Default: False
    """
    env_val = os.getenv("AUTUMN_INSECURE")
    if env_val is not None and str(env_val).strip() != "":
        return str(env_val).strip().lower() in ("1", "true", "yes", "y", "on")

    config = load_config() or {}

    # Preferred nested key: tls.insecure
    try:
        tls = config.get("tls")
        if isinstance(tls, dict) and "insecure" in tls:
            return bool(tls.get("insecure", False))
    except (ValueError, TypeError):
        pass

    # Back-compat: top-level insecure
    try:
        return bool(config.get("insecure", False))
    except (ValueError, TypeError):
        return False

