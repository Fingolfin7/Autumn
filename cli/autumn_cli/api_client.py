"""API client for communicating with AutumnWeb API."""

import requests
from typing import Optional, Dict, List, Any
from .config import get_api_key, get_base_url


class APIError(Exception):
    """Exception raised for API errors."""
    pass


class APIClient:
    """Client for AutumnWeb API."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or get_api_key()
        self.base_url = (base_url or get_base_url()).rstrip("/")
        
        if not self.api_key:
            raise APIError("API key not configured. Run 'autumn auth setup' first.")
    
    def _headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to API."""
        url = f"{self.base_url}{endpoint}"

        response = None
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._headers(),
                params=params,
                json=json,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response is not None and response.status_code == 401:
                raise APIError("Authentication failed. Check your API key.")
            try:
                error_data = response.json() if response is not None else {}
                error_msg = error_data.get("error", str(e))
                raise APIError(f"API error: {error_msg}")
            except APIError:
                raise
            except Exception:
                raise APIError(f"API error: {e}")
        except requests.exceptions.RequestException as e:
            # Keep network errors readable; urllib3 can be very verbose.
            host = None
            try:
                from urllib.parse import urlparse

                host = urlparse(url).hostname
            except Exception:
                host = None

            msg = str(e)
            # Common Windows DNS failure: getaddrinfo failed
            if "getaddrinfo failed" in msg or "NameResolutionError" in msg:
                hint = "DNS lookup failed"
            else:
                hint = "Network error"

            host_part = f" (host={host})" if host else ""
            raise APIError(
                f"{hint}{host_part}. Check your internet connection and base_url (autumn auth status). Details: {msg}"
            )

    def get_token_with_password(self, username_or_email: str, password: str) -> str:
        """Fetch an auth token using username/email + password.

        Uses DRF's built-in token endpoint at /get-auth-token/.
        """
        url = f"{self.base_url}/get-auth-token/"
        resp = requests.post(
            url,
            json={"username": username_or_email, "password": password},
            headers={"Accept": "application/json"},
            timeout=30,
        )
        if resp.status_code >= 400:
            try:
                data = resp.json()
                detail = data.get("detail") or data.get("error") or str(data)
            except Exception:
                detail = resp.text
            raise APIError(f"Login failed: {detail}")

        data = resp.json()
        token = data.get("token")
        if not token:
            raise APIError("Login failed: server did not return a token")
        return token

    def get_me(self) -> Dict[str, Any]:
        """Get the authenticated user's identity."""
        return self._request("GET", "/api/me/")

    def get_cached_me(self, *, ttl_seconds: int = 3600, refresh: bool = False) -> Dict[str, Any]:
        """Get cached /api/me response for greetings."""
        from .utils.user_cache import load_cached_user, save_cached_user

        if not refresh:
            snap = load_cached_user(ttl_seconds=ttl_seconds)
            if snap is not None:
                return {"user": snap.user, "cached": True}

        me = self.get_me()
        user = {
            "id": me.get("id"),
            "username": me.get("username"),
            "email": me.get("email"),
            "first_name": me.get("first_name", ""),
            "last_name": me.get("last_name", ""),
        }
        try:
            save_cached_user(user)
        except Exception:
            pass
        return {"user": user, "cached": False}

    def get_recent_activity_snippet(
        self,
        *,
        ttl_seconds: int = 600,
        refresh: bool = False,
        lookback_days: int = 14,
        max_sessions: int = 50,
    ) -> Dict[str, Any]:
        """Get a small recent-activity summary for greetings.

        Returns a dict like:
          {
            "last_project": str|None,
            "last_end": iso str|None,
            "today_project": str|None,  # last from today if any
            "longest_project": str|None,
            "longest_minutes": float|None,
            "most_frequent_project": str|None,  # most sessions in lookback
            "streak_days": int,  # consecutive days with sessions
          }

        Cached to avoid frequent API calls.
        """
        from .utils.recent_activity_cache import load_cached_activity, save_cached_activity

        if not refresh:
            snap = load_cached_activity(ttl_seconds=ttl_seconds)
            if snap is not None:
                return {**snap.info, "cached": True}

        # Pull recent sessions (saved) via search endpoint.
        from datetime import date, timedelta
        from collections import Counter

        start_date = (date.today() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        result = self.search_sessions(
            start_date=start_date,
            end_date=None,
            active=False,
            limit=max_sessions,
            offset=0,
        )
        sessions = result.get("sessions", [])

        last_project = None
        last_end = None
        today_project = None
        longest_project = None
        longest_minutes = None
        project_counts = Counter()
        session_dates = set()

        today_str = date.today().strftime("%Y-%m-%d")

        for s in sessions:
            p = s.get("p") or s.get("project")
            end = s.get("end") or s.get("end_time")
            dur = s.get("dur") or s.get("duration_minutes")

            if p:
                project_counts[p] += 1

            # Track session dates for streak
            if end:
                try:
                    end_date_only = end.split("T")[0]
                    session_dates.add(end_date_only)
                except Exception:
                    pass

            # Overall last
            if last_end is None and end:
                last_end = end
                last_project = p

            # Today's last
            if today_project is None and end and end.startswith(today_str):
                today_project = p

            # Longest
            try:
                dur_f = float(dur) if dur is not None else None
            except Exception:
                dur_f = None

            if dur_f is not None and (longest_minutes is None or dur_f > longest_minutes):
                longest_minutes = dur_f
                longest_project = p

        # Most frequent project
        most_frequent_project = project_counts.most_common(1)[0][0] if project_counts else None

        # Calculate streak (consecutive days up to today)
        streak_days = 0
        check_date = date.today()
        while True:
            check_str = check_date.strftime("%Y-%m-%d")
            if check_str in session_dates:
                streak_days += 1
                check_date -= timedelta(days=1)
            else:
                break

        info = {
            "last_project": last_project,
            "last_end": last_end,
            "today_project": today_project,
            "longest_project": longest_project,
            "longest_minutes": longest_minutes,
            "most_frequent_project": most_frequent_project,
            "streak_days": streak_days,
        }

        try:
            save_cached_activity(info)
        except Exception:
            pass

        return {**info, "cached": False}

    # Timer endpoints
    
    def start_timer(self, project: str, subprojects: Optional[List[str]] = None, note: Optional[str] = None) -> Dict:
        """Start a new timer."""
        data = {"project": project}
        if subprojects:
            data["subprojects"] = subprojects
        if note:
            data["note"] = note
        return self._request("POST", "/api/timer/start/", json=data)
    
    def stop_timer(self, session_id: Optional[int] = None, project: Optional[str] = None, note: Optional[str] = None) -> Dict:
        """Stop the current timer."""
        data = {}
        if session_id:
            data["session_id"] = session_id
        if project:
            data["project"] = project
        if note is not None:
            data["note"] = note
        return self._request("POST", "/api/timer/stop/", json=data)
    
    def get_timer_status(self, session_id: Optional[int] = None, project: Optional[str] = None) -> Dict:
        """Get status of active timer(s)."""
        params = {}
        if session_id:
            params["session_id"] = session_id
        if project:
            params["project"] = project
        return self._request("GET", "/api/timer/status/", params=params)
    
    def restart_timer(self, session_id: Optional[int] = None, project: Optional[str] = None) -> Dict:
        """Restart a timer."""
        data = {}
        if session_id:
            data["session_id"] = session_id
        if project:
            data["project"] = project
        return self._request("POST", "/api/timer/restart/", json=data)
    
    def delete_timer(self, session_id: Optional[int] = None) -> Dict:
        """Delete a timer."""
        params = {}
        if session_id:
            params["session_id"] = session_id
        return self._request("DELETE", "/api/timer/delete/", params=params)
    
    # Session endpoints
    
    def log_activity(
        self,
        period: Optional[str] = None,
        project: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict:
        """Get activity logs."""
        params = {"compact": "false"}
        if period:
            params["period"] = period
        if project:
            params["project"] = project
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if context:
            params["context"] = context
        if tags:
            params["tags"] = ",".join(tags)
        return self._request("GET", "/api/log/", params=params)
    
    def search_sessions(
        self,
        project: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        note_snippet: Optional[str] = None,
        active: Optional[bool] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict:
        """Search sessions."""
        params = {}
        if project:
            params["project"] = project
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if note_snippet:
            params["note_snippet"] = note_snippet
        if active is not None:
            params["active"] = str(active).lower()
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
        if context:
            params["context"] = context
        if tags:
            params["tags"] = ",".join(tags)
        return self._request("GET", "/api/sessions/search/", params=params)
    
    def track_session(
        self,
        project: str,
        start: str,
        end: str,
        subprojects: Optional[List[str]] = None,
        note: Optional[str] = None,
    ) -> Dict:
        """Track a completed session."""
        data = {
            "project": project,
            "start": start,
            "end": end,
        }
        if subprojects:
            data["subprojects"] = subprojects
        if note:
            data["note"] = note
        return self._request("POST", "/api/track/", json=data)
    
    # Project endpoints
    
    def list_projects_grouped(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict:
        """List projects grouped by status."""
        params = {"compact": "false"}  # Request full project metadata
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if context:
            params["context"] = context
        if tags:
            params["tags"] = ",".join(tags)
        return self._request("GET", "/api/projects/grouped/", params=params)
    
    def create_project(self, name: str, description: Optional[str] = None) -> Dict:
        """Create a new project."""
        data = {"name": name}
        if description:
            data["description"] = description
        return self._request("POST", "/api/create_project/", json=data)
    
    def list_subprojects(self, project: str) -> Dict:
        """List subprojects for a project."""
        params = {"project": project}
        return self._request("GET", "/api/subprojects/", params=params)
    
    # Chart/analytics endpoints
    
    def tally_by_sessions(
        self,
        project_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Get project totals (for charts)."""
        params = {}
        if project_name:
            params["project_name"] = project_name
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if context:
            params["context"] = context
        if tags:
            params["tags"] = ",".join(tags)
        return self._request("GET", "/api/tally_by_sessons/", params=params)  # Note: typo in API endpoint
    
    def tally_by_subprojects(
        self,
        project_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Get subproject totals (for charts)."""
        params = {"project_name": project_name}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if context:
            params["context"] = context
        if tags:
            params["tags"] = ",".join(tags)
        return self._request("GET", "/api/tally_by_subprojects/", params=params)

    def list_sessions(
        self,
        project_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict]:
        """List sessions (for charts)."""
        params = {}
        if project_name:
            params["project_name"] = project_name
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if context:
            params["context"] = context
        if tags:
            params["tags"] = ",".join(tags)
        return self._request("GET", "/api/list_sessions/", params=params)

    def list_contexts(self, compact: bool = True) -> Dict:
        """List available contexts for the authenticated user."""
        params = {"compact": str(compact).lower()}
        return self._request("GET", "/api/contexts/", params=params)

    def list_tags(self, compact: bool = True) -> Dict:
        """List available tags for the authenticated user."""
        params = {"compact": str(compact).lower()}
        return self._request("GET", "/api/tags/", params=params)

    def get_discovery_meta(self, *, ttl_seconds: int = 300, refresh: bool = False) -> Dict[str, Any]:
        """Get cached discovery metadata: contexts + tags.

        Returns: {"contexts": [...], "tags": [...], "cached": bool}

        This reduces repeated calls for commands that need to resolve filters.
        """
        from .utils.meta_cache import load_cached_snapshot, save_cached_snapshot

        if not refresh:
            snap = load_cached_snapshot(ttl_seconds=ttl_seconds)
            if snap is not None:
                return {"contexts": snap.contexts, "tags": snap.tags, "cached": True}

        contexts = self.list_contexts(compact=True).get("contexts", [])
        tags = self.list_tags(compact=True).get("tags", [])

        try:
            save_cached_snapshot(contexts, tags)
        except Exception:
            pass

        return {"contexts": contexts, "tags": tags, "cached": False}
