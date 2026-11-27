"""Local project bindings for Git checkouts."""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

from ..api_client import APIClient, APIError
from ..config import get_config_value, set_config_value


_BINDINGS_KEY = "checkout_projects"


def checkout_root() -> Path | None:
    """Find the current worktree root, including from a subdirectory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            encoding="utf-8",
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None
    # Strip Git's line ending while allowing whitespace in the checkout name.
    return Path(result.stdout.rstrip("\r\n")).resolve()


def _bindings() -> dict:
    value = get_config_value(_BINDINGS_KEY)
    return value if isinstance(value, dict) else {}


def _account_key(client: APIClient) -> str:
    # Use the server's identity so environment overrides, account renames
    # and token rotations cannot apply another user's checkout binding.
    user_id = client.get_me().get("id")
    if user_id is None:
        raise APIError("AutumnWeb returned no account ID.")
    return str(user_id)


def set_checkout_project(client: APIClient, root: Path, project_id: int) -> None:
    account = _account_key(client)
    bindings = _bindings()
    server = bindings.get(client.base_url)
    if not isinstance(server, dict):
        server = bindings[client.base_url] = {}
    path = os.path.normcase(str(root))
    checkout = server.get(path)
    if not isinstance(checkout, dict):
        checkout = server[path] = {}
    checkout[account] = project_id
    set_config_value(_BINDINGS_KEY, bindings)


def get_checkout_project(client: APIClient) -> str | None:
    """Return the current name of the project bound to this checkout."""
    server = _bindings().get(client.base_url)
    if not isinstance(server, dict) or not server:
        return None
    root = checkout_root()
    if root is None:
        return None
    checkout = server.get(os.path.normcase(str(root)))
    if not isinstance(checkout, dict) or not checkout:
        return None
    project_id = checkout.get(_account_key(client))
    if not isinstance(project_id, int):
        return None
    try:
        return client.get_project_by_id(project_id)["name"]
    except APIError as error:
        if error.code != "not_found":
            raise
        print("The linked project no longer exists. Run 'autumn here PROJECT' to link another.", file=sys.stderr)
        return None
