from __future__ import annotations

import types


def test_reminder_daemon_remind_in_wakes_before_poll(monkeypatch):
    """Regression: --remind-in shouldn't be delayed by --remind-poll.

    Prior behavior: daemon slept for poll_seconds (e.g. 30s), so a 5s remind-in
    would only fire after ~30s.

    This test stubs sleeping and session checking so the loop advances instantly.
    """

    from autumn_cli.commands import reminder_daemon as rd

    # Session remains active until we exit due to remind-in firing.
    monkeypatch.setattr(rd, "_is_session_active", lambda client, session_id: True)
    monkeypatch.setattr(rd, "_elapsed_str", lambda client, session_id: "0m")

    # Capture when we send a notification.
    calls = {"notify": 0, "slept": []}

    def fake_notify(*, title: str, message: str, subtitle=None):
        calls["notify"] += 1
        return types.SimpleNamespace(ok=True, supported=True, method="test")

    monkeypatch.setattr(rd, "send_notification", fake_notify)

    # Replace sleep to just advance time without actually waiting.
    def fake_sleep(seconds: int):
        calls["slept"].append(int(seconds))

    monkeypatch.setattr(rd, "sleep_seconds", fake_sleep)

    # APIClient isn't used because _is_session_active is patched.
    monkeypatch.setattr(rd, "APIClient", lambda: object())

    # Run: remind-in=5s, poll=30s → should sleep 5s first, send notification once, then exit.
    rd.main.callback(
        session_id=1,
        project="p",
        notify_title="Autumn",
        remind_in="5s",
        remind_every=None,
        for_=None,
        remind_message="Timer running: {project} ({elapsed})",
        remind_poll="30s",
        quiet=True,
    )

    assert calls["notify"] == 1
    assert calls["slept"], "daemon should have slept at least once"
    assert calls["slept"][0] == 5, "daemon should wake to fire remind-in before poll interval"
