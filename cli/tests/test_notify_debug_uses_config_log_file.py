from __future__ import annotations


def test_notify_debug_uses_config_log_file(monkeypatch, tmp_path):
    from autumn_cli.utils.notify_debug import log_notify_event

    log_path = tmp_path / "notify.log"

    # Ensure env var doesn't interfere.
    monkeypatch.delenv("AUTUMN_NOTIFY_LOG", raising=False)

    # Patch get_config_value used by notify_debug.
    monkeypatch.setattr(
        "autumn_cli.utils.notify_debug.get_config_value",
        lambda key, default=None: str(log_path) if key == "notify.log_file" else default,
    )

    log_notify_event("hello")

    assert log_path.exists()
    txt = log_path.read_text(encoding="utf-8")
    assert "hello" in txt

