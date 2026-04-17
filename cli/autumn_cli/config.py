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
ACCOUNTS_KEY = "accounts"
ACTIVE_ACCOUNT_KEY = "active_account"
ACCOUNT_CACHES_KEY = "account_caches"
ACCOUNT_ALIASES_KEY = "account_aliases"
LEGACY_CACHE_KEYS = (
    "user_cache",
    "activity_cache",
    "meta_cache",
    "projects_cache",
)


def ensure_config_dir():
    """Create config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _write_config_file(config: dict) -> None:
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


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
            data, changed = _migrate_legacy_config(data)
            if changed:
                _write_config_file(data)
            return data
    except (OSError, yaml.YAMLError):
        return {}


def save_config(config: dict):
    """Save configuration to file."""
    _write_config_file(config)


def _sanitize_account_name(name: str) -> str:
    cleaned = str(name or "").strip()
    if not cleaned:
        raise ValueError("Account name cannot be empty.")
    return cleaned


def _accounts_block(config: Optional[dict] = None) -> dict:
    cfg = config if config is not None else (load_config() or {})
    accounts = cfg.get(ACCOUNTS_KEY)
    return accounts if isinstance(accounts, dict) else {}


def _account_caches_block(config: Optional[dict] = None) -> dict:
    cfg = config if config is not None else (load_config() or {})
    caches = cfg.get(ACCOUNT_CACHES_KEY)
    return caches if isinstance(caches, dict) else {}


def _account_aliases_block(config: Optional[dict] = None) -> dict:
    cfg = config if config is not None else (load_config() or {})
    aliases = cfg.get(ACCOUNT_ALIASES_KEY)
    return aliases if isinstance(aliases, dict) else {}


def _account_entry_from_legacy(config: dict) -> Optional[tuple[str, dict[str, Any]]]:
    api_key = str(config.get("api_key") or "").strip()
    if not api_key:
        return None

    user_cache = config.get("user_cache")
    user = user_cache.get("user") if isinstance(user_cache, dict) else {}
    if not isinstance(user, dict):
        user = {}

    name = _sanitize_account_name(
        derive_account_name(
            username=user.get("username"),
            email=user.get("email"),
            base_url=str(config.get("base_url") or "http://localhost:8000"),
        )
    )

    entry: dict[str, Any] = {"api_key": api_key}
    if user.get("id") is not None:
        entry["user_id"] = user.get("id")
    if user.get("username"):
        entry["username"] = user.get("username")
    if user.get("email"):
        entry["email"] = user.get("email")
    if user.get("first_name"):
        entry["first_name"] = user.get("first_name")
    if user.get("last_name"):
        entry["last_name"] = user.get("last_name")
    return name, entry


def _merge_nested_dicts(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_nested_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _migrate_legacy_config(config: dict) -> tuple[dict, bool]:
    cfg = dict(config or {})
    changed = False

    accounts = _accounts_block(cfg)
    active_name = cfg.get(ACTIVE_ACCOUNT_KEY)
    if active_name not in accounts:
        legacy_account = _account_entry_from_legacy(cfg)
        if legacy_account is not None:
            migrated_name, migrated_entry = legacy_account
            accounts[migrated_name] = _merge_nested_dicts(accounts.get(migrated_name, {}), migrated_entry)
            cfg[ACCOUNTS_KEY] = accounts
            cfg[ACTIVE_ACCOUNT_KEY] = migrated_name
            active_name = migrated_name
            changed = True

    if active_name in accounts:
        legacy_account = _account_entry_from_legacy(cfg)
        active_entry = accounts.get(active_name) or {}
        if legacy_account is not None:
            migrated_name, migrated_entry = legacy_account
            should_rename = (
                active_name != migrated_name
                and migrated_name not in accounts
                and not active_entry.get("username")
                and not active_entry.get("email")
            )
            if should_rename:
                accounts[migrated_name] = _merge_nested_dicts(active_entry, migrated_entry)
                accounts.pop(active_name, None)

                caches = _account_caches_block(cfg)
                if active_name in caches:
                    caches[migrated_name] = caches.pop(active_name)
                    cfg[ACCOUNT_CACHES_KEY] = caches

                aliases = _account_aliases_block(cfg)
                if active_name in aliases:
                    aliases[migrated_name] = aliases.pop(active_name)
                    cfg[ACCOUNT_ALIASES_KEY] = aliases

                cfg[ACCOUNTS_KEY] = accounts
                cfg[ACTIVE_ACCOUNT_KEY] = migrated_name
                active_name = migrated_name
                changed = True

    if active_name in accounts:
        caches = _account_caches_block(cfg)
        scoped_caches = caches.get(active_name)
        if not isinstance(scoped_caches, dict):
            scoped_caches = {}
        for cache_key in LEGACY_CACHE_KEYS:
            legacy_block = cfg.get(cache_key)
            if isinstance(legacy_block, dict):
                if cache_key not in scoped_caches:
                    scoped_caches[cache_key] = legacy_block
                cfg.pop(cache_key, None)
                changed = True
        if scoped_caches:
            caches[active_name] = scoped_caches
            cfg[ACCOUNT_CACHES_KEY] = caches

        legacy_aliases = cfg.get("aliases")
        if isinstance(legacy_aliases, dict):
            alias_map = _account_aliases_block(cfg)
            scoped_aliases = alias_map.get(active_name)
            if not isinstance(scoped_aliases, dict):
                scoped_aliases = {}
            alias_map[active_name] = _merge_nested_dicts(scoped_aliases, legacy_aliases)
            cfg[ACCOUNT_ALIASES_KEY] = alias_map
            cfg.pop("aliases", None)
            changed = True

    cfg = _sync_active_account_fields(cfg)
    return cfg, changed


def _sync_active_account_fields(config: dict) -> dict:
    """Mirror the active account token into the top-level auth key."""
    accounts = _accounts_block(config)
    active_name = config.get(ACTIVE_ACCOUNT_KEY)
    active = accounts.get(active_name) if active_name else None

    if isinstance(active, dict):
        api_key = str(active.get("api_key") or "").strip()
        if api_key:
            config["api_key"] = api_key
        else:
            config.pop("api_key", None)
    elif accounts:
        config.pop("api_key", None)

    if not str(config.get("base_url") or "").strip():
        config["base_url"] = "http://localhost:8000"

    return config


def derive_account_name(*, username: Optional[str], email: Optional[str], base_url: str) -> str:
    identity = (username or email or "account").strip() or "account"
    return identity


def get_accounts() -> dict[str, dict[str, Any]]:
    """Return saved accounts keyed by account name."""
    return dict(_accounts_block())


def get_active_account_name() -> Optional[str]:
    """Return the active saved account name, if any."""
    config = load_config() or {}
    accounts = _accounts_block(config)
    active_name = config.get(ACTIVE_ACCOUNT_KEY)
    if active_name in accounts:
        return active_name
    return None


def get_active_account() -> Optional[dict[str, Any]]:
    """Return the active saved account, if any."""
    active_name = get_active_account_name()
    if not active_name:
        return None
    return get_accounts().get(active_name)


def get_active_cache_scope(config: Optional[dict] = None) -> Optional[str]:
    """Return the cache namespace key for the active saved account."""
    cfg = config if config is not None else (load_config() or {})
    accounts = _accounts_block(cfg)
    active_name = cfg.get(ACTIVE_ACCOUNT_KEY)
    if active_name in accounts:
        return active_name
    return None


def load_account_cache(cache_key: str) -> Optional[dict[str, Any]]:
    """Load a cache block for the active account."""
    cfg = load_config() or {}
    scope = get_active_cache_scope(cfg)
    caches = _account_caches_block(cfg)

    if scope and isinstance(caches.get(scope), dict):
        scoped_block = caches[scope].get(cache_key)
        if isinstance(scoped_block, dict):
            return dict(scoped_block)

    return None


def save_account_cache(cache_key: str, value: dict[str, Any]) -> None:
    """Save a cache block for the active account."""
    cfg = load_config() or {}
    scope = get_active_cache_scope(cfg)
    if not scope:
        return

    caches = _account_caches_block(cfg)
    scoped = caches.get(scope)
    if not isinstance(scoped, dict):
        scoped = {}
    scoped[cache_key] = dict(value)
    caches[scope] = scoped
    cfg[ACCOUNT_CACHES_KEY] = caches

    save_config(cfg)


def clear_account_cache(cache_key: str) -> None:
    """Clear a cache block for the active account."""
    cfg = load_config() or {}
    scope = get_active_cache_scope(cfg)
    changed = False

    if scope:
        caches = _account_caches_block(cfg)
        scoped = caches.get(scope)
        if isinstance(scoped, dict) and cache_key in scoped:
            scoped.pop(cache_key, None)
            changed = True
            if scoped:
                caches[scope] = scoped
            else:
                caches.pop(scope, None)
            if caches:
                cfg[ACCOUNT_CACHES_KEY] = caches
            else:
                cfg.pop(ACCOUNT_CACHES_KEY, None)

    if changed:
        save_config(cfg)


def get_account_aliases() -> dict[str, Any]:
    """Get aliases for the active account."""
    cfg = load_config() or {}
    scope = get_active_cache_scope(cfg)
    if not scope:
        return {}
    aliases = _account_aliases_block(cfg).get(scope)
    return dict(aliases) if isinstance(aliases, dict) else {}


def set_account_aliases(aliases: dict[str, Any]) -> None:
    """Replace aliases for the active account."""
    cfg = load_config() or {}
    scope = get_active_cache_scope(cfg)
    if not scope:
        return
    alias_map = _account_aliases_block(cfg)
    alias_map[scope] = dict(aliases or {})
    cfg[ACCOUNT_ALIASES_KEY] = alias_map
    save_config(cfg)


def save_account(
    *,
    account_name: str,
    api_key: str,
    user: Optional[dict[str, Any]] = None,
    make_active: bool = True,
) -> str:
    """Save or update a named account and optionally make it active."""
    name = _sanitize_account_name(account_name)
    config = load_config() or {}
    accounts = _accounts_block(config)

    entry: dict[str, Any] = {
        "api_key": api_key,
    }
    if isinstance(user, dict):
        if user.get("id") is not None:
            entry["user_id"] = user.get("id")
        if user.get("username"):
            entry["username"] = user.get("username")
        if user.get("email"):
            entry["email"] = user.get("email")
        if user.get("first_name"):
            entry["first_name"] = user.get("first_name")
        if user.get("last_name"):
            entry["last_name"] = user.get("last_name")

    accounts[name] = entry
    config[ACCOUNTS_KEY] = accounts
    if make_active:
        config[ACTIVE_ACCOUNT_KEY] = name

    config, _ = _migrate_legacy_config(config)
    save_config(_sync_active_account_fields(config))
    return name


def switch_account(account_name: str) -> dict[str, Any]:
    """Switch the active account to a saved account."""
    name = _sanitize_account_name(account_name)
    config = load_config() or {}
    accounts = _accounts_block(config)
    if name not in accounts:
        raise KeyError(name)

    config[ACTIVE_ACCOUNT_KEY] = name
    save_config(_sync_active_account_fields(config))
    return dict(accounts[name])


def remove_account(account_name: str) -> bool:
    """Remove a saved account. Returns True if it existed."""
    name = _sanitize_account_name(account_name)
    config = load_config() or {}
    accounts = _accounts_block(config)
    if name not in accounts:
        return False

    accounts.pop(name, None)
    caches = _account_caches_block(config)
    if name in caches:
        caches.pop(name, None)
        if caches:
            config[ACCOUNT_CACHES_KEY] = caches
        else:
            config.pop(ACCOUNT_CACHES_KEY, None)

    aliases = _account_aliases_block(config)
    if name in aliases:
        aliases.pop(name, None)
        if aliases:
            config[ACCOUNT_ALIASES_KEY] = aliases
        else:
            config.pop(ACCOUNT_ALIASES_KEY, None)

    if accounts:
        config[ACCOUNTS_KEY] = accounts
    else:
        config.pop(ACCOUNTS_KEY, None)

    if config.get(ACTIVE_ACCOUNT_KEY) == name:
        config[ACTIVE_ACCOUNT_KEY] = next(iter(accounts), None)
        if config[ACTIVE_ACCOUNT_KEY] is None:
            config.pop(ACTIVE_ACCOUNT_KEY, None)

    save_config(_sync_active_account_fields(config))
    return True


def list_accounts() -> list[dict[str, Any]]:
    """Return saved accounts for display, active account first."""
    accounts = get_accounts()
    active_name = get_active_account_name()
    rows: list[dict[str, Any]] = []
    for name, entry in accounts.items():
        row = dict(entry)
        row["name"] = name
        row["active"] = name == active_name
        rows.append(row)

    rows.sort(key=lambda item: (not item["active"], item["name"].lower()))
    return rows


def get_api_key() -> Optional[str]:
    """Get API key from config or environment variable."""
    # Environment variable takes precedence
    env_key = os.getenv("AUTUMN_API_KEY")
    if env_key:
        return env_key
    
    # Fall back to config file
    config = load_config()
    active = get_active_account()
    if isinstance(active, dict) and active.get("api_key"):
        return active.get("api_key")
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
    active_name = config.get(ACTIVE_ACCOUNT_KEY)
    accounts = _accounts_block(config)
    if active_name in accounts and isinstance(accounts.get(active_name), dict):
        accounts[active_name]["api_key"] = api_key
        config[ACCOUNTS_KEY] = accounts
    config["api_key"] = api_key
    save_config(_sync_active_account_fields(config))


def set_base_url(base_url: str):
    """Set base URL in config file."""
    config = load_config()
    config["base_url"] = base_url.rstrip("/")
    save_config(_sync_active_account_fields(config))


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


def get_banner_enabled() -> bool:
    """Whether to show the ASCII art banner when running `autumn` with no subcommand.

    Controlled by config.yaml key `ui.banner: true/false`.
    Default: True
    """
    config = load_config() or {}
    try:
        ui = config.get("ui")
        if isinstance(ui, dict) and "banner" in ui:
            return bool(ui.get("banner", True))
    except (ValueError, TypeError):
        pass
    return True


def set_banner_enabled(value: bool) -> None:
    """Enable or disable the ASCII art banner."""
    set_config_value("ui.banner", bool(value))


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
