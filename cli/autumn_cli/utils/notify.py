"""Cross-platform desktop notifications.

Goal: best-effort notifications without adding heavy dependencies.

Strategy:
- macOS: `osascript` (native)
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


@dataclass(frozen=True)
class NotifyResult:
    ok: bool
    supported: bool
    method: str
    error: Optional[str] = None


def send_notification(*, title: str, message: str, subtitle: Optional[str] = None) -> NotifyResult:
    system = platform.system()

    if system == "Darwin":
        return _notify_macos(title=title, message=message, subtitle=subtitle)

    if system == "Linux":
        return _notify_linux(title=title, message=message)

    if system == "Windows":
        return _notify_windows(title=title, message=message)

    return NotifyResult(ok=False, supported=False, method=system, error="Unsupported OS")


def _notify_macos(*, title: str, message: str, subtitle: Optional[str]) -> NotifyResult:
    osascript = shutil.which("osascript")
    if osascript is None:
        return NotifyResult(ok=False, supported=False, method="osascript", error="osascript not found")

    # Escape quotes for AppleScript.
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    t = esc(title)
    m = esc(message)

    if subtitle:
        st = esc(subtitle)
        script = f'display notification "{m}" with title "{t}" subtitle "{st}"'
    else:
        script = f'display notification "{m}" with title "{t}"'

    try:
        subprocess.run([str(osascript), "-e", script], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return NotifyResult(ok=True, supported=True, method="osascript")
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        return NotifyResult(ok=False, supported=True, method="osascript", error=err.strip() or str(e))


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
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Autumn')
$notifier.Show($toast)
"""

    try:
        subprocess.run(
            [str(ps), "-NoProfile", "-NonInteractive", "-Command", script, title, message],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env={**os.environ},
        )
        return NotifyResult(ok=True, supported=True, method="powershell")
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        return NotifyResult(ok=False, supported=True, method="powershell", error=err.strip() or str(e))
