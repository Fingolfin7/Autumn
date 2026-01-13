from __future__ import annotations


def test_send_notification_prefers_plyer_non_macos(monkeypatch):
    from autumn_cli.utils import notify as n

    # Force non-macOS behavior so this test is deterministic on CI/dev machines.
    monkeypatch.setattr(n.platform, "system", lambda: "Linux")

    calls = {"plyer": 0, "fallback": 0}

    class FakePlyerNotification:
        @staticmethod
        def notify(**kwargs):
            calls["plyer"] += 1

    class FakePlyerModule:
        notification = FakePlyerNotification

    monkeypatch.setitem(__import__("sys").modules, "plyer", FakePlyerModule)

    # Make sure fallback doesn't run if plyer succeeds.
    monkeypatch.setattr(n, "_notify_linux", lambda **kwargs: calls.__setitem__("fallback", 1) or None)

    res = n.send_notification(title="t", message="m")
    assert res.ok is True
    assert res.method == "plyer"
    assert calls["plyer"] == 1
    assert calls["fallback"] == 0
