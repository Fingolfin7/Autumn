"""Cross-platform desktop notifications.

Goal: best-effort notifications without adding heavy dependencies.

Strategy:
- Preferred (all OSes): `plyer` (single Python API)
- Fallbacks:
  - macOS: `terminal-notifier` with automatic Homebrew installation
  - Linux: `notify-send` if available
  - Windows: `powershell` toast notification (best-effort)

If the platform helper isn't available, we no-op and report `supported=False`.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import platform
import shutil
import subprocess
from typing import Optional
from pathlib import Path
try:
    import importlib.resources as importlib_resources
except ImportError:
    import importlib_resources

from .notify_debug import log_notify_event


@dataclass(frozen=True)
class NotifyResult:
    ok: bool
    supported: bool
    method: str
    error: Optional[str] = None


def send_notification(*, title: str, message: str, subtitle: Optional[str] = None) -> NotifyResult:
    """Send a notification.

    We prefer using `plyer` because it's a single cross-platform API.
    We then fall back to platform-specific helpers, since plyer can be missing
    optional backends depending on the environment.
    """

    system = platform.system()

    # macOS: plyer commonly depends on pyobjus and may not be usable.
    # Prefer the native osascript approach first.
    if system == "Darwin":
        return _notify_macos(title=title, message=message, subtitle=subtitle)

    # 1) Preferred (non-macOS): plyer
    try:
        from plyer import notification as plyer_notification

        # plyer doesn't support subtitle on all platforms.
        # Try to use our custom icon if available (Windows needs ICO format)
        icon_path = None
        if system == "Windows":
            try:
                icon_path = _get_asset_path("autumn_icon.ico")
                if not icon_path.exists():
                    icon_path = None
            except Exception:
                icon_path = None

        kwargs = {"title": str(title), "message": str(message), "app_name": "Autumn"}
        if icon_path:
            kwargs["app_icon"] = str(icon_path)

        plyer_notification.notify(**kwargs)
        log_notify_event("plyer notify: ok")
        return NotifyResult(ok=True, supported=True, method="plyer")
    except Exception as e:
        # Don't fail hard; use fallbacks.
        log_notify_event(f"plyer notify: failed: {e!r}")

    # 2) Fallbacks
    if system == "Linux":
        return _notify_linux(title=title, message=message)

    if system == "Windows":
        return _notify_windows(title=title, message=message)

    return NotifyResult(ok=False, supported=False, method=system, error="Unsupported OS")


def _get_asset_path(asset_name: str) -> Path:
    """Get the absolute path to an asset file.

    Handles both development mode (editable install) and installed mode.
    """
    # Try using importlib.resources (Python 3.9+)
    try:
        with importlib_resources.path("autumn_cli.assets", asset_name) as path:
            return Path(path)
    except (ImportError, FileNotFoundError, AttributeError, Exception):
        # Fallback for development mode or when package isn't installed normally
        module_dir = Path(__file__).parent.parent
        assets_dir = module_dir / "assets"
        asset_path = assets_dir / asset_name
        if asset_path.exists():
            return asset_path
        # Last resort: return the path anyway and let it fail if it doesn't exist
        return asset_path


def _notify_macos(*, title: str, message: str, subtitle: Optional[str]) -> NotifyResult:
    # Use terminal-notifier for reliable macOS notifications

    # 1) Check if terminal-notifier is installed
    terminal_notifier = shutil.which("terminal-notifier")

    # 2) If not installed, try to install via Homebrew
    if terminal_notifier is None:
        brew = shutil.which("brew")
        if brew:
            try:
                proc = subprocess.run(
                    [brew, "install", "terminal-notifier"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=300,
                )
                terminal_notifier = shutil.which("terminal-notifier")
                log_notify_event("macos notify: installed terminal-notifier via brew")
            except Exception as e:
                err_bytes = e.stderr if hasattr(e, 'stderr') else b""
                err = err_bytes.decode("utf-8", errors="replace") if err_bytes else str(e)
                log_notify_event(f"macos notify: brew install failed: {err}")
                return NotifyResult(
                    ok=False,
                    supported=False,
                    method="terminal-notifier",
                    error=f"Failed to install terminal-notifier. Please run: brew install terminal-notifier"
                )
        else:
            log_notify_event("macos notify: brew not found")
            return NotifyResult(
                ok=False,
                supported=False,
                method="terminal-notifier",
                error="Homebrew not found. Install terminal-notifier manually: https://github.com/julienXX/terminal-notifier"
            )

    # 3) Get the icon path from assets
    icon_path = _get_asset_path("autumn_icon.png")

    # 4) Build the command
    cmd = [
        str(terminal_notifier),
        "-title", str(title),
        "-message", str(message),
        "-appIcon", str(icon_path),
        "-sender", "com.apple.terminal",
    ]

    if subtitle:
        cmd.extend(["-subtitle", str(subtitle)])

    # 5) Run the command
    try:
        proc = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        log_notify_event("macos notify: ok (terminal-notifier)")
        return NotifyResult(ok=True, supported=True, method="terminal-notifier")
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        log_notify_event(f"macos notify: failed: {err}")
        return NotifyResult(ok=False, supported=True, method="terminal-notifier", error=err.strip())
    except Exception as e:
        log_notify_event(f"macos notify: exception: {e!r}")
        return NotifyResult(ok=False, supported=True, method="terminal-notifier", error=str(e))


def _notify_linux(*, title: str, message: str) -> NotifyResult:
    # notify-send is the de-facto standard for many desktop environments.
    notify_send = shutil.which("notify-send")
    if notify_send is None:
        return NotifyResult(ok=False, supported=False, method="notify-send", error="notify-send not found")

    try:
        subprocess.run(
            [str(notify_send), title, message],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        return NotifyResult(ok=True, supported=True, method="notify-send")
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        return NotifyResult(ok=False, supported=True, method="notify-send", error=err.strip() or str(e))


def _notify_windows(*, title: str, message: str) -> NotifyResult:
    # Best-effort toast via PowerShell.
    # This doesn't require external deps but may fail on locked-down systems.
    ps = shutil.which("pwsh") or shutil.which("powershell")
    if ps is None:
        return NotifyResult(ok=False, supported=False, method="powershell", error="powershell not found")

    # Get the icon path if available
    try:
        icon_path = _get_asset_path("autumn_icon.ico")
        if not icon_path.exists():
            icon_path = None
    except Exception:
        icon_path = None

    # Use Windows 10+ toast notification APIs.
    # If it fails, we report it but don't crash the CLI.
    script = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null

$template = @"
<toast>
  <visual>
    <binding template='ToastGeneric'>
      <text>$($args[0])</text>
      <text>$($args[1])</text>
    </binding>
  </visual>
</toast>
"@

$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)

"""

    # Add image element to the template if icon is available
    if icon_path:
        script = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null

$template = @"
<toast>
  <visual>
    <binding template='ToastGeneric'>
      <image placement='appLogoOverride' src='$($args[2])'/>
      <text>$($args[0])</text>
      <text>$($args[1])</text>
    </binding>
  </visual>
</toast>
"@

$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)

"""

    script += r"""
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Autumn')
$notifier.Show($toast)
"""

    # Build command arguments
    cmd_args = [str(ps), "-NoProfile", "-NonInteractive", "-Command", script, title, message]
    if icon_path:
        cmd_args.append(str(icon_path))

    try:
        subprocess.run(
            cmd_args,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env={**os.environ},
        )
        return NotifyResult(ok=True, supported=True, method="powershell")
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        return NotifyResult(ok=False, supported=True, method="powershell", error=err.strip() or str(e))
