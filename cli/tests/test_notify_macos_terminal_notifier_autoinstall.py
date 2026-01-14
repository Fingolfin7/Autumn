from __future__ import annotations

import subprocess


def test_macos_terminal_notifier_tries_brew_install_when_missing(monkeypatch, tmp_path):
    """If terminal-notifier isn't present but brew is, we should try `brew install terminal-notifier`.

    This stays unit-testable by patching which() and subprocess.run().
    """

    from autumn_cli.utils import notify as n

    # Force macOS behavior regardless of runner OS.
    monkeypatch.setattr(n.platform, "system", lambda: "Darwin")

    # Ensure icon path exists so we can assert -appIcon wiring without depending on package data.
    icon = tmp_path / "autumn_icon.png"
    icon.write_bytes(b"png")
    monkeypatch.setattr(n, "_get_asset_path", lambda name: icon)

    calls: list[list[str]] = []

    def fake_which(cmd: str):
        # First lookup: terminal-notifier missing.
        if cmd == "terminal-notifier":
            # After "brew install", pretend it exists.
            if any(c[:2] == ["/opt/homebrew/bin/brew", "install"] for c in calls):
                return "/usr/local/bin/terminal-notifier"
            return None
        if cmd == "brew":
            return "/opt/homebrew/bin/brew"
        return None

    def fake_run(cmd, check=False, stdout=None, stderr=None, timeout=None, env=None):
        calls.append([str(x) for x in cmd])
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(n.shutil, "which", fake_which)
    monkeypatch.setattr(n.subprocess, "run", fake_run)

    res = n.send_notification(title="t", message="m")

    assert res.supported is True
    assert res.ok is True
    assert res.method == "terminal-notifier"

    # Ensure we attempted brew install.
    assert any(c[:3] == ["/opt/homebrew/bin/brew", "install", "terminal-notifier"] for c in calls)

    # Ensure terminal-notifier invocation includes the icon when available.
    tn_calls = [c for c in calls if c and c[0].endswith("terminal-notifier")]
    assert tn_calls, "Expected a terminal-notifier call"
    assert "-appIcon" in tn_calls[-1]
    assert "-contentImage" in tn_calls[-1]


def test_macos_terminal_notifier_returns_helpful_message_when_brew_missing(monkeypatch):
    from autumn_cli.utils import notify as n

    monkeypatch.setattr(n.platform, "system", lambda: "Darwin")

    def fake_which(cmd: str):
        if cmd in {"terminal-notifier", "brew"}:
            return None
        return None

    monkeypatch.setattr(n.shutil, "which", fake_which)

    res = n.send_notification(title="t", message="m")

    assert res.ok is False
    assert res.supported is False
    assert res.method == "terminal-notifier"
    assert res.error
    assert "brew install terminal-notifier" in res.error or "Homebrew" in res.error
