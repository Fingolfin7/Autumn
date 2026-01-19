from __future__ import annotations
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from collections import Counter
import threading
import time

from ...api_client import APIClient, APIError


class DashboardState:
    def __init__(self, client: APIClient):
        self.client = client
        self.active_session: Optional[Dict[str, Any]] = None
        self.weekly_tally: List[Dict[str, Any]] = []
        self.daily_intensity: Dict[str, float] = {}
        self.top_subprojects: List[Dict[str, Any]] = []
        self.most_active_project: Optional[str] = None
        self.trends: Dict[str, Any] = {
            "total_time": 0.0,
            "change_pct": 0.0,
            "streak": 0,
            "avg_daily": 0.0,
        }
        self.logs: List[str] = []
        self.last_refresh: float = 0
        self.refresh_interval: int = 60  # seconds
        self._lock = threading.Lock()
        self.is_loading: bool = False
        self.week_offset: int = 0  # 0 = this week, -1 = last week, etc.

    def add_log(self, message: str):
        with self._lock:
            timestamp = datetime.now().strftime("%H:%M")
            # Handle multiline messages by splitting them
            for line in str(message).splitlines():
                if line.strip():
                    self.logs.append(f"[{timestamp}] {line}")

            while len(self.logs) > 5:
                self.logs.pop(0)

    def refresh(self, force: bool = False):
        if not force and time.time() - self.last_refresh < self.refresh_interval:
            return

        self.is_loading = True
        try:
            # 1. Fetch active timer
            status = self.client.get_timer_status()
            if status.get("ok") and status.get("active", 0) > 0:
                # API returns a list of sessions
                sessions = status.get("sessions") or status.get("session")
                if isinstance(sessions, list) and sessions:
                    self.active_session = sessions[0]
                elif isinstance(sessions, dict):
                    self.active_session = sessions
                else:
                    self.active_session = None
            else:
                self.active_session = None

            # 2. Fetch weekly tally
            today = date.today()
            # Calculate Monday of the target week
            target_monday = (
                today
                - timedelta(days=today.weekday())
                + timedelta(weeks=self.week_offset)
            )
            target_sunday = target_monday + timedelta(days=6)

            start_date_str = target_monday.strftime("%Y-%m-%d")
            end_date_str = target_sunday.strftime("%Y-%m-%d")

            tally = self.client.tally_by_sessions(
                start_date=start_date_str, end_date=end_date_str
            )
            self.weekly_tally = sorted(
                tally, key=lambda x: x.get("total_time", 0), reverse=True
            )

            # 3. Calculate Daily Intensity and Trends from logs
            # Fetch target week + previous week for trends
            start_for_trends = target_monday - timedelta(days=7)
            logs_res = self.client.log_activity(
                start_date=start_for_trends.strftime("%Y-%m-%d"),
                end_date=end_date_str,
                period=None,
            )
            all_logs = logs_res.get("logs", [])
            self.add_log(f"Fetched {len(all_logs)} logs")

            daily_totals = Counter()
            this_week_total = 0.0
            last_week_total = 0.0

            for log in all_logs:
                # API uses duration_minutes or dur
                dur = float(log.get("duration_minutes") or log.get("dur") or 0)
                # API uses start_time or start
                log_start = log.get("start_time") or log.get("start") or ""
                if not log_start:
                    continue

                # Take only the YYYY-MM-DD part
                log_date_str = log_start.split("T")[0]

                try:
                    # Defensive parsing for various date formats
                    if "-" in log_date_str:
                        log_date = date.fromisoformat(log_date_str[:10])
                    else:
                        continue

                    if target_monday <= log_date <= target_sunday:
                        daily_totals[log_date_str] += dur
                        this_week_total += dur
                    elif (
                        (target_monday - timedelta(days=7)) <= log_date < target_monday
                    ):
                        last_week_total += dur
                except Exception as e:
                    # self.add_log(f"Date error: {log_date_str} - {str(e)}")
                    continue

            # Fill in intensity for the 7 days of the target week
            self.daily_intensity = {}
            for i in range(7):
                d = target_monday + timedelta(days=i)
                d_str = d.strftime("%Y-%m-%d")
                # Use the abbreviated day name (Mon, Tue, etc)
                self.daily_intensity[d.strftime("%a")] = daily_totals.get(d_str, 0.0)

            # Trends
            change = 0.0
            if last_week_total > 0:
                change = ((this_week_total - last_week_total) / last_week_total) * 100
            elif this_week_total > 0:
                change = 100.0  # From zero to something

            # Get streak
            activity = self.client.get_recent_activity_snippet()

            self.trends = {
                "total_time": this_week_total,
                "change_pct": change,
                "streak": activity.get("streak_days", 0),
                "avg_daily": this_week_total / 7,
            }

            # 4. Top Subprojects
            if self.weekly_tally:
                self.most_active_project = self.weekly_tally[0].get("name")
                if self.most_active_project:
                    sub_tally = self.client.tally_by_subprojects(
                        self.most_active_project,
                        start_date=start_date_str,
                        end_date=end_date_str,
                    )
                    self.top_subprojects = sorted(
                        sub_tally, key=lambda x: x.get("total_time", 0), reverse=True
                    )[:5]
            else:
                self.most_active_project = None
                self.top_subprojects = []

            self.last_refresh = time.time()
        except Exception as e:
            self.add_log(f"Refresh error: {str(e)}")
        finally:
            self.is_loading = False
