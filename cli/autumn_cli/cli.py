"""Main CLI entry point for Autumn CLI."""

import click
from datetime import datetime

from .utils.console import console
from .utils.greetings import build_greeting
from .utils.banner import cell_len_markup, pad_right_markup
from .config import (
    get_api_key,
    get_base_url,
    set_api_key,
    set_base_url,
    load_config,
    save_config,
    save_account,
    list_accounts,
    switch_account as switch_saved_account,
    remove_account,
    get_active_account_name,
    derive_account_name,
    get_greeting_general_weight,
    get_greeting_activity_weight,
    get_greeting_moon_cameo_weight,
    get_banner_enabled,
)
from .api_client import APIClient, APIError
from .commands.timer import start, stop, restart, delete, status as timer_status
from .commands.sessions import log, track, edit_session
from .commands.projects import projects_list, new_project, subprojects, mark, rename, delete_project, delete_sub, totals, project_details, merge, merge_subs
from .commands.charts import chart

from .commands.meta import context, tag
from .commands.meta import meta
from .commands.config_cmd import config
from .commands.open_cmd import open_cmd
from .commands.resume_cmd import resume
from .commands.notify_cmd import notify_cmd
from .commands.remind_cmd import remind
from .commands.reminders_cmd import reminders
from .commands.export_cmd import export
from .commands.meta import meta_audit
from .commands.alias_cmd import alias


@click.group(invoke_without_command=True)
@click.version_option(version="1.0.0")
@click.pass_context
def cli(ctx: click.Context):
    """Autumn CLI - Command-line interface for AutumnWeb."""
    # Health check for reminders (orphaned/missed)
    if ctx.invoked_subcommand != "reminder-daemon":
        try:
            from .utils.reminders_registry import check_reminders_health

            health_msgs = check_reminders_health()
            for msg in health_msgs:
                console.print(msg)
        except (OSError, IOError, ImportError):
            pass

    if ctx.invoked_subcommand is None:
        try:
            client = APIClient()
            me = client.get_cached_me(ttl_seconds=3600, refresh=False).get("user", {})
            username = (me.get("username") or "there").strip() or "there"
            base_url = get_base_url()

            # Get recent activity (best-effort, cached)
            activity = None
            try:
                activity = client.get_recent_activity_snippet(
                    ttl_seconds=600, refresh=False
                )
            except APIError:
                pass

            # Build contextual greeting (one line)
            g = build_greeting(
                datetime.now(),
                activity=activity,
                general_weight=get_greeting_general_weight(),
                activity_weight=get_greeting_activity_weight(),
                moon_weight=get_greeting_moon_cameo_weight(),
            )

            # Build greeting text (plain, for width calculation)
            greeting_plain = g.line.format(username=username)
            greeting_styled = g.line.format(username=f"[autumn.user]{username}[/]")

            # Show ASCII banner with greeting inside if enabled
            if get_banner_enabled():
                title_text = "autumn"
                title_styled = f"🍁 [bold]{title_text}[/]"

                # Include left padding in the measured content.
                title_line = "  " + title_styled
                greeting_line = "  " + greeting_styled

                # Derive box width from the *rendered* (markup) lines.
                measured_width = max(
                    cell_len_markup(title_line, console=console),
                    cell_len_markup(greeting_line, console=console),
                )
                content_width = measured_width

                top = f"┌{'─' * content_width}┐"
                bottom = f"└{'─' * content_width}┘"

                title_line = pad_right_markup(title_line, content_width, console=console)
                greeting_line = pad_right_markup(greeting_line, content_width, console=console)

                console.print(f"[dim]{top}[/]")
                # NOTE: The extra space before the right border is intentional.
                console.print(f"[dim]│[/]{title_line}[dim]│[/]")
                console.print(f"[dim]│[/]{greeting_line}[dim]│[/]")
                console.print(f"[dim]{bottom}[/]")

        except APIError:
            # Fallback when not authenticated
            if get_banner_enabled():
                title_line = "  🍁 [bold]autumn[/]"
                msg_line = "  Run `autumn auth login` to get started."

                measured_width = max(
                    cell_len_markup(title_line, console=console),
                    cell_len_markup(msg_line, console=console),
                )
                content_width = measured_width

                title_line = pad_right_markup(title_line, content_width, console=console)
                msg_line = pad_right_markup(msg_line, content_width, console=console)

                console.print(f"[dim]┌{'─' * content_width}┐[/]")
                console.print(f"[dim]│[/]{title_line}[dim]│[/]")
                console.print(f"[dim]│[/]{msg_line}[dim]│[/]")
                console.print(f"[dim]└{'─' * content_width}┘[/]")
            else:
                click.echo("Autumn CLI")
                click.echo(
                    "Run `autumn auth setup` (API key) or `autumn auth login` (password) to get started."
                )


@cli.group()
def auth():
    """Authentication and configuration commands."""
    pass


@auth.command()
@click.option(
    "--api-key", help="Your AutumnWeb API token (can also paste when prompted)"
)
@click.option("--base-url", help="AutumnWeb base URL (can also paste when prompted)")
def setup(api_key: str, base_url: str):
    """Configure API key and base URL."""
    # If not provided as arguments, prompt for them (hide_input=False allows pasting)
    if not api_key:
        api_key = click.prompt("API Key", hide_input=False)
    if not base_url:
        base_url = click.prompt("Base URL", default="http://localhost:8000")

    set_base_url(base_url)
    set_api_key(api_key)

    account_name = None
    try:
        client = APIClient(api_key=api_key, base_url=base_url)
        me = client.get_cached_me(ttl_seconds=0, refresh=True).get("user", {})
        account_name = save_account(
            account_name=derive_account_name(
                username=me.get("username"),
                email=me.get("email"),
                base_url=base_url,
            ),
            api_key=api_key,
            user=me,
            make_active=True,
        )
        _clear_auth_caches()
    except APIError:
        pass

    click.echo("Configuration saved successfully!")
    click.echo(f"Base URL: {base_url}")
    click.echo("API key saved (hidden)")
    if account_name:
        click.echo(f"Saved account: {account_name}")

    # Verify the configuration
    try:
        verify()
    except (APIError, click.Abort):
        click.echo(
            "\nWarning: Could not verify API key. Please check your credentials."
        )


def _warn_if_insecure_tls() -> None:
    """Print a single warning if TLS verification is disabled."""
    try:
        from .config import get_insecure

        if get_insecure():
            click.echo(
                "Warning: TLS certificate verification is disabled (tls.insecure=true). "
                "This is insecure; prefer enabling verification when possible.",
                err=True,
            )
    except (ImportError, ValueError, TypeError):
        pass


def _clear_auth_caches() -> None:
    from .utils.meta_cache import clear_cached_snapshot
    from .utils.projects_cache import clear_cached_projects
    from .utils.user_cache import clear_cached_user
    from .utils.recent_activity_cache import clear_cached_activity

    clear_cached_snapshot()
    clear_cached_projects()
    clear_cached_user()
    clear_cached_activity()


@auth.command()
def verify():
    """Verify API key and connection."""
    try:
        _warn_if_insecure_tls()
        api_key = get_api_key()
        base_url = get_base_url()

        if not api_key:
            click.echo(
                "Error: API key not configured. Run 'autumn auth setup' first.",
                err=True,
            )
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
    active_account = get_active_account_name()
    if active_account:
        click.echo(f"  Active account: {active_account}")
    if api_key:
        click.echo(f"  API key: {api_key[:8]}... (configured)")
    else:
        click.echo("  API key: Not configured")
    click.echo(f"  Saved accounts: {len(list_accounts())}")

    # Test connection
    if api_key:
        try:
            client = APIClient()
            client.get_timer_status()
            click.echo("  Connection: ✓ Working")
        except APIError:
            click.echo("  Connection: ✗ Failed")


@auth.command()
@click.option("--username", help="Username or email")
@click.option("--password", help="Password (will prompt if omitted)")
@click.option("--base-url", help="AutumnWeb base URL")
def login(username: str, password: str, base_url: str):
    """Login with username/email + password and store the API token."""
    _warn_if_insecure_tls()

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
    client = APIClient(api_key=token, base_url=base_url)

    # Validate by calling /api/me
    try:
        me = client.get_cached_me(ttl_seconds=0, refresh=True).get("user", {})
        account_name = save_account(
            account_name=derive_account_name(
                username=me.get("username"),
                email=me.get("email"),
                base_url=base_url,
            ),
            api_key=token,
            user=me,
            make_active=True,
        )
        _clear_auth_caches()
        click.echo(f"✓ Logged in as {me.get('username') or username}.")
        click.echo(f"  Saved account: {account_name}")
    except APIError:
        set_api_key(token)
        _clear_auth_caches()
        click.echo("✓ Logged in.")


@auth.command()
def logout():
    """Logout by clearing the stored API token and cached user metadata."""
    config = load_config()
    persisted_active_account = config.get("active_account")
    active_account = get_active_account_name()
    if persisted_active_account:
        remove_account(active_account)
    else:
        if "api_key" in config:
            config.pop("api_key", None)
            save_config(config)

    _clear_auth_caches()

    if persisted_active_account:
        click.echo(f"Logged out account '{active_account}'.")
        next_account = get_active_account_name()
        if next_account:
            click.echo(f"Switched to saved account '{next_account}'.")
        else:
            click.echo("Run `autumn auth login` to sign in again.")
    else:
        click.echo("Logged out. Run `autumn auth login` to sign in again.")


@auth.command("accounts")
def auth_accounts():
    """List saved accounts."""
    accounts = list_accounts()
    click.echo(f"Base URL: {get_base_url()}")
    if not accounts:
        click.echo("No saved accounts.")
        return

    click.echo("Saved accounts:")
    for entry in accounts:
        marker = "*" if entry.get("active") else " "
        username = entry.get("username") or entry.get("email") or entry.get("name")
        email = entry.get("email")
        detail = f" ({email})" if email and email != username else ""
        click.echo(f" {marker} {entry['name']}: {username}{detail}")


@auth.command("switch")
@click.argument("account_name")
def auth_switch(account_name: str):
    """Switch to a saved account."""
    try:
        switch_saved_account(account_name)
    except KeyError:
        click.echo(f"Error: Unknown account '{account_name}'.", err=True)
        raise click.Abort()

    _clear_auth_caches()

    try:
        client = APIClient()
        me = client.get_cached_me(ttl_seconds=0, refresh=True).get("user", {})
        click.echo(
            f"Switched to {account_name} ({me.get('username') or me.get('email') or 'unknown user'})."
        )
    except APIError:
        click.echo(f"Switched to {account_name}.")


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
cli.add_command(edit_session, name="edit")

# Project commands
cli.add_command(projects_list, name="projects")
cli.add_command(projects_list, name="p")
cli.add_command(subprojects, name="subprojects")
cli.add_command(subprojects, name="subs")
cli.add_command(new_project, name="new")
cli.add_command(mark, name="mark")
cli.add_command(rename, name="rename")
cli.add_command(delete_project, name="delete-project")
cli.add_command(delete_sub, name="delete-sub")
cli.add_command(totals, name="totals")
cli.add_command(project_details, name="project")
cli.add_command(merge, name="merge")
cli.add_command(merge_subs, name="merge-subs")


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
cli.add_command(notify_cmd, name="notify")
cli.add_command(remind, name="remind")
cli.add_command(reminders, name="reminders")

# Data commands
cli.add_command(export, name="export")
cli.add_command(meta_audit, name="audit")

# Alias management
cli.add_command(alias, name="alias")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
