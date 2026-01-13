from __future__ import annotations

from autumn_cli.utils.notify import send_notification


def test_send_notification_returns_structured_result():
    # We don't assert ok/support on CI since availability depends on OS.
    res = send_notification(title="Autumn", message="Test notification from unit tests")
    assert isinstance(res.ok, bool)
    assert isinstance(res.supported, bool)
    assert isinstance(res.method, str)

