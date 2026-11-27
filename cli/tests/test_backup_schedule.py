import plistlib
from datetime import datetime, time
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from click.testing import CliRunner

from autumn_cli import config
from autumn_cli.cli import cli
from autumn_cli.commands import backup as commands
from autumn_cli.utils.backup_schedule import BackupSchedule, _mac_plist, _windows_task


@pytest.fixture
def saved_accounts(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.yaml")
    config.save_config({
        "base_url": "https://example.test",
        "active_account": "personal",
        "accounts": {
            "personal": {"api_key": "test-token-a", "username": "personal"},
            "work": {"api_key": "test-token-b", "username": "work"},
        },
    })
    return config.CONFIG_FILE


def test_set_defaults_to_daily_and_skips_all_insights(tmp_path, saved_accounts, monkeypatch):
    installed = []
    monkeypatch.setattr(commands, "install_schedule", installed.append)
    destination = tmp_path / "Backups with spaces"
    original = saved_accounts.read_bytes()

    result = CliRunner().invoke(
        cli, ["--account", "work", "backup", "schedule", "set", "--at", "02:00", "--dir", str(destination)],
    )

    assert result.exit_code == 0, result.output
    assert installed == [BackupSchedule("work", destination, time(2), None, False, False)]
    assert "daily at 02:00" in result.output
    assert saved_accounts.read_bytes() == original
    arguments = installed[0].command()
    assert arguments[-2:] == ["--dir", str(destination)]
    assert all("test-token" not in arg for arg in arguments)


def test_set_weekly_with_opted_in_files_then_show_and_remove(saved_accounts, monkeypatch):
    installed, removed = [], []
    monkeypatch.setattr(commands, "install_schedule", installed.append)
    monkeypatch.setattr(commands, "show_schedule", lambda account: f"Schedule for {account}")
    monkeypatch.setattr(commands, "remove_schedule", removed.append)
    runner = CliRunner()
    prefix = ["backup", "schedule"]
    created = runner.invoke(cli, prefix + ["set", "--at", "06:15", "--on", "Sunday", "--insights", "--attachments"])
    assert created.exit_code == 0, created.output
    assert "every Sunday at 06:15" in created.output
    assert installed[0].command()[-2:] == ["--insights", "--attachments"]
    assert runner.invoke(cli, prefix + ["show"]).output.strip() == "Schedule for personal"
    assert runner.invoke(cli, prefix + ["remove"]).exit_code == 0
    assert removed == ["personal"]


@pytest.mark.parametrize("prefix", [["backup"], ["backup", "schedule", "set", "--at", "06:15"]])
def test_files_alone_require_insights(saved_accounts, prefix):
    result = CliRunner().invoke(cli, prefix + ["--attachments"])
    assert result.exit_code == 2
    assert "--attachments requires --insights" in result.output


def test_native_specs_preserve_time_day_arguments_and_local_identity(tmp_path):
    spec = BackupSchedule("personal", tmp_path / "Backups & media", time(2, 15), "sunday", True, False)
    xml = ET.fromstring(_windows_task(spec, "S-1-5-21-100", datetime(2026, 11, 29, 3)))
    assert xml.findtext(".//{*}StartBoundary") == "2026-12-06T02:15:00"
    assert xml.find(".//{*}Sunday") is not None
    assert xml.findtext(".//{*}LogonType") == "InteractiveToken"
    assert xml.findtext(".//{*}StartWhenAvailable") == "true"
    assert f'"{spec.directory}"' in xml.findtext(".//{*}Arguments")

    plist = plistlib.loads(_mac_plist(spec))
    assert plist["StartCalendarInterval"] == {"Weekday": 0, "Hour": 2, "Minute": 15}
    assert plist["ProgramArguments"][-3:] == ["--dir", str(spec.directory), "--insights"]
    assert Path(plist["ProgramArguments"][0]).is_absolute()
