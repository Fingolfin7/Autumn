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

    def add_log(self, message: str):
        with self._lock:
            timestamp = datetime.now().strftime("%H:%M")
            self.logs.append(f"[{timestamp}] {message}")
            if len(self.logs) > 5:
                self.logs.pop(0)

    def refresh(self, force: bool = False):
        if not force and time.time() - self.last_refresh < self.refresh_interval:
            return

        self.is_loading = True
        try:
            # 1. Fetch active timer
            status = self.client.get_timer_status()
            if status.get("ok") and status.get("active", 0) > 0:
                self.active_session = status.get("sessions", [None])[0]
            else:
                self.active_session = None

            # 2. Fetch weekly tally
            # Get current week start (Monday)
            today = date.today()
            start_of_week = today - timedelta(days=today.weekday())
            start_date_str = start_of_week.strftime("%Y-%m-%d")

            tally = self.client.tally_by_sessions(start_date=start_date_str)
            self.weekly_tally = sorted(
                tally, key=lambda x: x.get("total_time", 0), reverse=True
            )

            # 3. Calculate Daily Intensity and Trends from logs
            # Fetch last 14 days to calculate change vs last week
            start_of_14_days = today - timedelta(days=13)
            logs_res = self.client.log_activity(
                start_date=start_of_14_days.strftime("%Y-%m-%d"), period=None
            )
            all_logs = logs_res.get("logs", [])

            # Aggregate by day
            daily_totals = Counter()
            this_week_total = 0.0
            last_week_total = 0.0

            seven_days_ago = today - timedelta(days=6)

            for log in all_logs:
                dur = float(log.get("dur") or log.get("duration_minutes") or 0)
                log_date_str = log.get("start", "").split("T")[0]
                try:
                    log_date = date.fromisoformat(log_date_str)
                    daily_totals[log_date_str] += dur

                    if log_date >= start_of_week:
                        this_week_total += dur
                    elif log_date >= (start_of_week - timedelta(days=7)):
                        last_week_total += dur
                except Exception:
                    continue

            # Fill in intensity for last 7 days
            self.daily_intensity = {}
            for i in range(7):
                d = today - timedelta(days=6 - i)
                d_str = d.strftime("%Y-%m-%d")
                self.daily_intensity[d.strftime("%a")] = daily_totals.get(d_str, 0.0)

            # Trends
            change = 0.0
            if last_week_total > 0:
                change = ((this_week_total - last_week_total) / last_week_total) * 100

            # Get streak from recent activity snippet (already has logic)
            activity = self.client.get_recent_activity_snippet()

            self.trends = {
                "total_time": this_week_total,
                "change_pct": change,
                "streak": activity.get("streak_days", 0),
                "avg_daily": this_week_total / (today.weekday() + 1)
                if today.weekday() >= 0
                else 0,
            }

            # 4. Top Subprojects for most active project
            if self.weekly_tally:
                self.most_active_project = self.weekly_tally[0].get("name")
                if self.most_active_project:
                    sub_tally = self.client.tally_by_subprojects(
                        self.most_active_project, start_date=start_date_str
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
