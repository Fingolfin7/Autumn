"""Main CLI entry point for Autumn CLI."""

import click
from datetime import datetime

from .utils.console import console
from .utils.greetings import build_greeting
from .config import (
    get_api_key,
    get_base_url,
    set_api_key,
    set_base_url,
    load_config,
    save_config,
    get_greeting_activity_weight,
    get_greeting_moon_cameo_weight,
)
from .api_client import APIClient, APIError
from .commands.timer import start, stop, restart, delete, status as timer_status
from .commands.sessions import log, track
from .commands.projects import projects_list, new_project
from .commands.charts import chart
from .commands.meta import context, tag
from .commands.meta import meta
from .commands.config_cmd import config
from .commands.open_cmd import open_cmd
from .commands.resume_cmd import resume


@click.group(invoke_without_command=True)
@click.version_option(version="0.1.0")
@click.pass_context
def cli(ctx: click.Context):
    """Autumn CLI - Command-line interface for AutumnWeb."""
    if ctx.invoked_subcommand is None:
        try:
            client = APIClient()
            me = client.get_cached_me(ttl_seconds=3600, refresh=False).get("user", {})
            username = (me.get("username") or "there").strip() or "there"
            base_url = get_base_url()

            # Get recent activity (best-effort, cached)
            activity = None
            try:
                activity = client.get_recent_activity_snippet(ttl_seconds=600, refresh=False)
            except Exception:
                pass

            # Build contextual greeting (one line)
            g = build_greeting(
                datetime.now(),
                activity=activity,
                activity_weight=get_greeting_activity_weight(),
                moon_cameo_weight=get_greeting_moon_cameo_weight(),
            )

            # Print greeting with username inserted (styled)
            greeting_line = g.line.format(username=f"[autumn.user]{username}[/]")
            console.print(greeting_line)

            # Print connection info
            console.print(f"You're connected to [autumn.time]{base_url}[/].")


        except Exception:
            click.echo("Autumn CLI")
            click.echo("Run `autumn auth setup` (API key) or `autumn auth login` (password) to get started.")


@cli.group()
def auth():
    """Authentication and configuration commands."""
    pass


@auth.command()
@click.option("--api-key", help="Your AutumnWeb API token (can also paste when prompted)")
@click.option("--base-url", help="AutumnWeb base URL (can also paste when prompted)")
def setup(api_key: str, base_url: str):
    """Configure API key and base URL."""
    # If not provided as arguments, prompt for them (hide_input=False allows pasting)
    if not api_key:
        api_key = click.prompt("API Key", hide_input=False)
    if not base_url:
        base_url = click.prompt("Base URL", default="http://localhost:8000")
    
    set_api_key(api_key)
    set_base_url(base_url)
    click.echo("Configuration saved successfully!")
    click.echo(f"Base URL: {base_url}")
    click.echo("API key saved (hidden)")
    
    # Verify the configuration
    try:
        verify()
    except:
        click.echo("\nWarning: Could not verify API key. Please check your credentials.")


@auth.command()
def verify():
    """Verify API key and connection."""
    try:
        api_key = get_api_key()
        base_url = get_base_url()
        
        if not api_key:
            click.echo("Error: API key not configured. Run 'autumn auth setup' first.", err=True)
            raise click.Abort()
        
        # Try to verify by making a simple API call
        client = APIClient()
        result = client.get_timer_status()
        
        click.echo("✓ Authentication successful!")
        click.echo(f"  Base URL: {base_url}")
        click.echo(f"  API key: {api_key[:8]}...")
    except APIError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@auth.command()
def status():
    """Show current configuration status."""
    config = load_config()
    api_key = get_api_key()
    base_url = get_base_url()
    
    click.echo("Configuration:")
    click.echo(f"  Base URL: {base_url}")
    if api_key:
        click.echo(f"  API key: {api_key[:8]}... (configured)")
    else:
        click.echo("  API key: Not configured")
    
    # Test connection
    if api_key:
        try:
            client = APIClient()
            client.get_timer_status()
            click.echo("  Connection: ✓ Working")
        except:
            click.echo("  Connection: ✗ Failed")


@auth.command()
@click.option("--username", help="Username or email")
@click.option("--password", help="Password (will prompt if omitted)")
@click.option("--base-url", help="AutumnWeb base URL")
def login(username: str, password: str, base_url: str):
    """Login with username/email + password and store the API token."""
    from .utils.meta_cache import clear_cached_snapshot
    from .utils.user_cache import clear_cached_user

    if not username:
        username = click.prompt("Username or email", hide_input=False)
    if not base_url:
        base_url = click.prompt("Base URL", default=get_base_url())
    if not password:
        password = click.prompt("Password", hide_input=True)

    # Use a temporary client (no api key required) just for token retrieval
    temp = APIClient(api_key="dummy", base_url=base_url)
    token = temp.get_token_with_password(username, password)

    set_base_url(base_url)
    set_api_key(token)

    # Clear caches so they reload as the new user
    clear_cached_snapshot()
    clear_cached_user()

    # Validate by calling /api/me
    try:
        client = APIClient()
        me = client.get_cached_me(ttl_seconds=0, refresh=True).get("user", {})
        click.echo(f"✓ Logged in as {me.get('username') or username}.")
    except Exception:
        click.echo("✓ Logged in.")


@auth.command()
def logout():
    """Logout by clearing the stored API token and cached user metadata."""
    from .utils.meta_cache import clear_cached_snapshot
    from .utils.user_cache import clear_cached_user

    config = load_config()
    if "api_key" in config:
        config.pop("api_key", None)
        save_config(config)

    clear_cached_snapshot()
    clear_cached_user()

    click.echo("Logged out. Run `autumn auth login` to sign in again.")


# Register commands directly (flat structure)
# Timer commands
cli.add_command(start, name="start")
cli.add_command(stop, name="stop")
cli.add_command(timer_status, name="status")  # Timer status
cli.add_command(restart, name="restart")
cli.add_command(delete, name="delete")

# Session commands
cli.add_command(log, name="log")
cli.add_command(log, name="ls")
cli.add_command(track, name="track")

# Project commands
cli.add_command(projects_list, name="projects")
cli.add_command(projects_list, name="p")
cli.add_command(new_project, name="new")

# Chart command
cli.add_command(chart, name="chart")

# Metadata discovery
cli.add_command(context, name="context")
cli.add_command(tag, name="tag")
cli.add_command(meta, name="meta")

# Config commands
cli.add_command(config, name="config")

# Convenience commands
cli.add_command(open_cmd, name="open")
cli.add_command(resume, name="resume")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
