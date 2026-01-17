"""Config commands for Autumn CLI.

These commands edit ~/.autumn/config.yaml.
We keep them simple and safe:
- show: print current config (minus secrets by default)
- get/set: access values by dotted path
- greeting: tune greeting-specific knobs
"""

from __future__ import annotations

import json
import click
import subprocess
import sys
import shutil

from ..config import (
    load_config,
    get_config_value,
    set_config_value,
    get_greeting_general_weight,
    get_greeting_activity_weight,
    get_greeting_moon_cameo_weight,
    set_greeting_weights,
    ensure_config_dir,
    CONFIG_FILE,
)
from ..utils.console import console


def _redact(cfg: dict) -> dict:
    cfg = dict(cfg or {})
    if "api_key" in cfg and cfg["api_key"]:
        cfg["api_key"] = "***"
    return cfg


@click.group()
def config() -> None:
    """View and edit Autumn CLI configuration."""


@config.command("show")
@click.option("--raw", is_flag=True, help="Show config including secrets (dangerous)")
@click.option("--json", "json_out", is_flag=True, help="Output as JSON")
def config_show(raw: bool, json_out: bool) -> None:
    """Show the current config."""
    cfg = load_config() or {}
    cfg_out = cfg if raw else _redact(cfg)

    if json_out:
        console.print_json(data=cfg_out)
        return

    # YAML-ish pretty print via Rich JSON for readability
    console.print_json(data=cfg_out)


@config.command("open")
def config_open() -> None:
    """Open the config file in the system file explorer (cross-platform).

    On Windows this will open Explorer and select the file. On macOS it will
    reveal the file in Finder. On Linux it will open the containing folder with
    the user's default file manager (selection support varies by environment).
    """
    # Ensure config directory exists and create the file if missing so the user
    # can see it in their file manager.
    ensure_config_dir()
    cfg_path = CONFIG_FILE
    try:
        if not cfg_path.exists():
            cfg_path.touch()

        if sys.platform.startswith("win"):
            # explorer /select,<path>
            subprocess.run(["explorer", f"/select,{str(cfg_path)}"], check=False)
        elif sys.platform == "darwin":
            # open -R <path> reveals the file in Finder
            subprocess.run(["open", "-R", str(cfg_path)], check=False)
        else:
            # Linux / other: open the containing folder. Try common launchers.
            dirpath = str(cfg_path.parent)
            opener = shutil.which("xdg-open")
            if not opener:
                opener = shutil.which("gio")
            if opener:
                if opener.endswith("gio"):
                    subprocess.run([opener, "open", dirpath], check=False)
                else:
                    subprocess.run([opener, dirpath], check=False)
            else:
                # As a last resort, open the file with the default application
                import webbrowser

                webbrowser.open(str(cfg_path))

        console.print(f"[autumn.ok]Opened[/] {cfg_path}")
    except Exception as e:
        console.print(f"[autumn.err]Failed to open file explorer: {e}[/]")


@config.command("get")
@click.argument("key")
@click.option("--default", "default_value", default=None, help="Default if key is missing")
def config_get(key: str, default_value: str | None) -> None:
    """Get a config value by dotted path."""
    val = get_config_value(key, default_value)
    # try to render scalars nicely
    if isinstance(val, (dict, list)):
        console.print_json(data=val)
    else:
        console.print(str(val))


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.option(
    "--type",
    "type_",
    type=click.Choice(["str", "int", "float", "bool", "json"], case_sensitive=False),
    default="str",
    help="How to parse VALUE",
)
def config_set(key: str, value: str, type_: str) -> None:
    """Set a config value by dotted path."""
    type_ = type_.lower()

    if type_ == "int":
        parsed = int(value)
    elif type_ == "float":
        parsed = float(value)
    elif type_ == "bool":
        parsed = value.strip().lower() in ("1", "true", "yes", "y", "on")
    elif type_ == "json":
        parsed = json.loads(value)
    else:
        parsed = value

    set_config_value(key, parsed)
    console.print(f"[autumn.ok]Updated[/] {key}")


@config.group("greeting")
def config_greeting() -> None:
    """Greeting configuration."""


@config_greeting.command("show")
def greeting_show() -> None:
    """Show greeting-related settings."""
    console.print_json(
        data={
            "greeting_general_weight": get_greeting_general_weight(),
            "greeting_activity_weight": get_greeting_activity_weight(),
            "greeting_moon_cameo_weight": get_greeting_moon_cameo_weight(),
        }
    )


@config_greeting.command("set")
@click.option("--general-weight", type=float, default=None, help="0..1 (how often general lines are used)")
@click.option("--activity-weight", type=float, default=None, help="0..1 (how often activity is referenced)")
@click.option("--moon-cameo-weight", type=float, default=None, help="0..1 (how often moon lines appear)")
def greeting_set(
    general_weight: float | None,
    activity_weight: float | None,
    moon_cameo_weight: float | None,
) -> None:
    """Set greeting knobs."""
    old_vals = {
        "greeting_general_weight": get_greeting_general_weight(),
        "greeting_activity_weight": get_greeting_activity_weight(),
        "greeting_moon_cameo_weight": get_greeting_moon_cameo_weight(),
    }

    updated = set_greeting_weights(
        general=general_weight,
        activity=activity_weight,
        moon_cameo=moon_cameo_weight,
    )

    # Warn if we had to clamp (either per-key or total-sum adjustment)
    requested = {
        k: v
        for k, v in (
            ("greeting_general_weight", general_weight),
            ("greeting_activity_weight", activity_weight),
            ("greeting_moon_cameo_weight", moon_cameo_weight),
        )
        if v is not None
    }
    clamped_any = any(abs(float(updated[k]) - float(requested[k])) > 1e-9 for k in requested)
    if clamped_any:
        console.print(
            "[autumn.warn]Weights were clamped to keep total ≤ 1.0.[/]"
        )

    if not updated:
        console.print("[autumn.warn]No values provided.[/]")
        return

    console.print_json(data=updated)
