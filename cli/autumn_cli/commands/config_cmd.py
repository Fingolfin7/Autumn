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

from ..config import (
    load_config,
    get_config_value,
    set_config_value,
    get_greeting_activity_weight,
    set_greeting_activity_weight,
    get_greeting_moon_cameo_weight,
    set_greeting_moon_cameo_weight,
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
            "greeting_activity_weight": get_greeting_activity_weight(),
            "greeting_moon_cameo_weight": get_greeting_moon_cameo_weight(),
        }
    )


@config_greeting.command("set")
@click.option("--activity-weight", type=float, default=None, help="0..1 (how often activity is referenced)")
@click.option("--moon-cameo-weight", type=float, default=None, help="0..1 (how often non-full/new moon appears)")
def greeting_set(activity_weight: float | None, moon_cameo_weight: float | None) -> None:
    """Set greeting knobs."""
    updated = {}
    if activity_weight is not None:
        updated["greeting_activity_weight"] = set_greeting_activity_weight(activity_weight)
    if moon_cameo_weight is not None:
        updated["greeting_moon_cameo_weight"] = set_greeting_moon_cameo_weight(moon_cameo_weight)

    if not updated:
        console.print("[autumn.warn]No values provided.[/]")
        return

    console.print_json(data=updated)
