"""Register backups with the signed-in user's native scheduler."""

import csv
import hashlib
import os
import plistlib
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from xml.etree import ElementTree as ET

from ..errors import AutumnError


WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


@dataclass(frozen=True)
class BackupSchedule:
    account: str
    directory: Path
    at: time
    weekday: str | None
    insights: bool
    attachments: bool

    def command(self, *, windowless: bool = False) -> list[str]:
        python = Path(sys.executable)
        pythonw = python.with_name("pythonw.exe")
        if windowless and pythonw.is_file():
            python = pythonw
        command = [
            str(python), "-m", "autumn_cli", "--account", self.account,
            "backup", "--dir", str(self.directory),
        ]
        if self.insights:
            command.append("--insights")
        if self.attachments:
            command.append("--attachments")
        return command


def _label(account: str, user: str = "") -> str:
    digest = hashlib.sha256(f"{user}/{account}".encode()).hexdigest()[:20]
    return f"org.autumn.backup.{digest}"


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, errors="replace",
            stdin=subprocess.DEVNULL, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AutumnError(f"Could not run {args[0]}: {error}") from error
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise AutumnError(f"{args[0]}: {detail}")
    return result


def _next_run(at: time, weekday: str | None, now: datetime) -> datetime:
    days = (WEEKDAYS.index(weekday) - now.weekday()) % 7 if weekday else 0
    start = datetime.combine(now.date() + timedelta(days=days), at)
    return start if start > now else start + timedelta(days=7 if weekday else 1)


def _windows_task(spec: BackupSchedule, sid: str, now: datetime) -> bytes:
    root = ET.Element("Task", xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task", version="1.2")
    registration = ET.SubElement(root, "RegistrationInfo")
    ET.SubElement(registration, "Description").text = f"Download an Autumn account backup for {spec.account}"
    trigger = ET.SubElement(ET.SubElement(root, "Triggers"), "CalendarTrigger")
    ET.SubElement(trigger, "StartBoundary").text = _next_run(spec.at, spec.weekday, now).isoformat(timespec="seconds")
    if spec.weekday:
        schedule = ET.SubElement(trigger, "ScheduleByWeek")
        ET.SubElement(schedule, "WeeksInterval").text = "1"
        ET.SubElement(ET.SubElement(schedule, "DaysOfWeek"), spec.weekday.capitalize())
    else:
        schedule = ET.SubElement(trigger, "ScheduleByDay")
        ET.SubElement(schedule, "DaysInterval").text = "1"
    principal = ET.SubElement(ET.SubElement(root, "Principals"), "Principal", id="AutumnUser")
    ET.SubElement(principal, "UserId").text = sid
    ET.SubElement(principal, "LogonType").text = "InteractiveToken"
    ET.SubElement(principal, "RunLevel").text = "LeastPrivilege"
    settings = ET.SubElement(root, "Settings")
    ET.SubElement(settings, "MultipleInstancesPolicy").text = "IgnoreNew"
    ET.SubElement(settings, "DisallowStartIfOnBatteries").text = "false"
    ET.SubElement(settings, "StopIfGoingOnBatteries").text = "false"
    ET.SubElement(settings, "StartWhenAvailable").text = "true"
    action = ET.SubElement(ET.SubElement(root, "Actions", Context="AutumnUser"), "Exec")
    launcher, *arguments = spec.command(windowless=True)
    ET.SubElement(action, "Command").text = launcher
    ET.SubElement(action, "Arguments").text = subprocess.list2cmdline(arguments)
    return ET.tostring(root, encoding="utf-16", xml_declaration=True)


def _windows_sid() -> str:
    result = _run("whoami.exe", "/user", "/fo", "csv", "/nh")
    row = next(csv.reader(result.stdout.splitlines()), [])
    if len(row) != 2 or not row[1].startswith("S-1-"):
        raise AutumnError("Could not read the current Windows user's SID.")
    return row[1]


def _mac_plist(spec: BackupSchedule) -> bytes:
    calendar = {"Hour": spec.at.hour, "Minute": spec.at.minute}
    if spec.weekday:
        calendar["Weekday"] = (WEEKDAYS.index(spec.weekday) + 1) % 7
    return plistlib.dumps({
        "Label": _label(spec.account),
        "ProgramArguments": spec.command(),
        "StartCalendarInterval": calendar,
    })


def _mac_agent(account: str) -> tuple[Path, str]:
    label = _label(account)
    return Path.home() / "Library" / "LaunchAgents" / f"{label}.plist", f"gui/{os.getuid()}"


def _atomic_write(path: Path, content: bytes) -> None:
    temporary = None
    try:
        with NamedTemporaryFile(dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(content)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def install_schedule(spec: BackupSchedule) -> None:
    if sys.platform == "win32":
        sid = _windows_sid()
        temporary = None
        try:
            with NamedTemporaryFile(suffix=".xml", delete=False) as file:
                temporary = Path(file.name)
                file.write(_windows_task(spec, sid, datetime.now()))
            _run("schtasks.exe", "/Create", "/TN", _label(spec.account, sid), "/XML", str(temporary), "/F")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return
    if sys.platform != "darwin":
        raise AutumnError("Autumn backup scheduling is available on Windows and macOS.")

    path, domain = _mac_agent(spec.account)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = path.read_bytes() if path.exists() else None
    old_job = _run("launchctl", "print", f"{domain}/{_label(spec.account)}", check=False)
    if old_job.returncode == 0:
        _run("launchctl", "bootout", f"{domain}/{_label(spec.account)}")
    try:
        _atomic_write(path, _mac_plist(spec))
        _run("launchctl", "bootstrap", domain, str(path))
    except (AutumnError, OSError):
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            _atomic_write(path, previous)
            if old_job.returncode == 0:
                _run("launchctl", "bootstrap", domain, str(path))
        raise


def show_schedule(account: str) -> str:
    if sys.platform == "win32":
        return _run("schtasks.exe", "/Query", "/TN", _label(account, _windows_sid()), "/FO", "LIST", "/V").stdout.strip()
    if sys.platform == "darwin":
        _, domain = _mac_agent(account)
        return _run("launchctl", "print", f"{domain}/{_label(account)}").stdout.strip()
    raise AutumnError("Autumn backup scheduling is available on Windows and macOS.")


def remove_schedule(account: str) -> None:
    if sys.platform == "win32":
        _run("schtasks.exe", "/Delete", "/TN", _label(account, _windows_sid()), "/F")
    elif sys.platform == "darwin":
        path, domain = _mac_agent(account)
        job = f"{domain}/{_label(account)}"
        if _run("launchctl", "print", job, check=False).returncode == 0:
            _run("launchctl", "bootout", job)
        path.unlink(missing_ok=True)
    else:
        raise AutumnError("Autumn backup scheduling is available on Windows and macOS.")
