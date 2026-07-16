"""API client for communicating with AutumnWeb API."""

import json
import time
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from .config import get_api_key, get_base_url, get_wake_retry, get_wake_timeout_seconds
from .utils.console import console


_UNSET = object()


class APIError(Exception):
    """Exception raised for API errors."""

    pass


class APIClient:
    """Client for AutumnWeb API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        quiet: bool = False,
        wake_retry: Optional[bool] = None,
    ):
        self.api_key = api_key or get_api_key()
        self.base_url = (base_url or get_base_url()).rstrip("/")
        self.quiet = quiet
        # None -> defer to config; False forces fast-fail (for opportunistic
        # background checks that must never block on a sleeping server).
        self._wake_retry_override = wake_retry
        self._server_awake = False

        # Only support a simple TLS verify toggle.
        # Safe-by-default: verify=True unless explicitly configured insecure.
        self._verify: bool = True
        try:
            from .config import get_insecure

            self._verify = not bool(get_insecure())
        except (ImportError, ValueError, TypeError):
            self._verify = True

        # If we're explicitly running insecure, hide urllib3's noisy warning.
        # We'll surface a single, friendlier message in `autumn auth` commands instead.
        if self._verify is False:
            try:
                import warnings

                from urllib3.exceptions import InsecureRequestWarning

                warnings.simplefilter("ignore", InsecureRequestWarning)
            except ImportError:
                pass

        if not self.api_key:
            raise APIError("API key not configured. Run 'autumn auth setup' first.")

    def _headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _chart_date_param(self, value: Optional[str]) -> Optional[str]:
        """Normalize chart-only legacy date params to MM-DD-YYYY."""
        if not value:
            return value
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%m-%d-%Y")
        except ValueError:
            return value

    @staticmethod
    def _is_dns_error(error: requests.exceptions.ConnectionError) -> bool:
        """Return whether a connection error is specifically DNS resolution."""
        message = str(error)
        return "getaddrinfo failed" in message or "NameResolutionError" in message

    def _is_wake_trigger(
        self,
        method: str,
        *,
        retry_safe: bool = False,
        response: Optional[requests.Response] = None,
        error: Optional[requests.exceptions.RequestException] = None,
    ) -> bool:
        """Return whether this failure is consistent with a sleeping server."""
        if response is not None:
            return response.status_code in (502, 503, 504)
        if isinstance(error, requests.exceptions.ConnectionError):
            return not self._is_dns_error(error)
        if isinstance(error, requests.exceptions.ConnectTimeout):
            return True
        retry_eligible = method.upper() in ("GET", "HEAD") or retry_safe
        return isinstance(error, requests.exceptions.ReadTimeout) and retry_eligible

    def _wake_server(self) -> bool:
        """Poll the unauthenticated health endpoint until the server is ready."""
        if not self.quiet:
            console.print(
                "[autumn.warn]Server appears to be asleep (free instance). "
                "Waking it up - this usually takes about a minute...[/]"
            )

        deadline = time.monotonic() + get_wake_timeout_seconds()
        delays = (3, 5, 8, 10)
        attempt = 0
        health_url = f"{self.base_url}/healthz/"

        while True:
            try:
                response = requests.get(health_url, timeout=10, verify=self._verify)
                if response.status_code == 200:
                    self._server_awake = True
                    if not self.quiet:
                        console.print("[autumn.ok]Server is up - retrying...[/]")
                    return True
            except requests.exceptions.RequestException:
                pass

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            delay = delays[min(attempt, len(delays) - 1)]
            time.sleep(min(delay, remaining))
            attempt += 1

    def _wake_retry_enabled(self) -> bool:
        if self._wake_retry_override is not None:
            return self._wake_retry_override
        return get_wake_retry()

    def _ensure_server_awake(self) -> None:
        """Confirm the server is awake before sending a mutation."""
        if self._server_awake:
            return

        health_url = f"{self.base_url}/healthz/"
        try:
            response = requests.get(health_url, timeout=5, verify=self._verify)
            if response.status_code == 200:
                self._server_awake = True
                return
        except requests.exceptions.RequestException:
            pass

        if self._wake_server():
            self._server_awake = True
            return

        raise APIError(
            "Server did not wake up in time. Try again in a minute, or check "
            f"{self.base_url}."
        )

    @staticmethod
    def _uncertain_mutation_error() -> APIError:
        return APIError(
            "The server was unreachable while processing this command. It may or "
            "may not have been applied - check with 'autumn status' or 'autumn log' "
            "before re-running."
        )

    def _http(
        self, method: str, url: str, *, retry_safe: bool = False, **kwargs: Any
    ) -> requests.Response:
        """Send one API request, waking a sleeping hosted server when needed."""
        method = method.upper()
        wake_retry_enabled = self._wake_retry_enabled()
        retry_eligible = method in ("GET", "HEAD") or retry_safe

        if wake_retry_enabled and method not in ("GET", "HEAD"):
            self._ensure_server_awake()

        try:
            response = requests.request(method=method, url=url, **kwargs)
        except requests.exceptions.RequestException as error:
            if not wake_retry_enabled or not self._is_wake_trigger(
                method, retry_safe=retry_safe, error=error
            ):
                raise
            if not retry_eligible:
                raise self._uncertain_mutation_error()
            response = None

        if response is not None:
            if response.status_code < 400:
                self._server_awake = True
            if not self._is_wake_trigger(
                method, retry_safe=retry_safe, response=response
            ) or not wake_retry_enabled:
                return response
            if not retry_eligible:
                raise self._uncertain_mutation_error()

        if not self._wake_server():
            raise APIError(
                "Server did not wake up in time. Try again in a minute, or check "
                f"{self.base_url}."
            )

        try:
            retry_response = requests.request(method=method, url=url, **kwargs)
        except requests.exceptions.RequestException as error:
            if self._is_wake_trigger(method, retry_safe=retry_safe, error=error):
                raise APIError(
                    "Server did not wake up in time. Try again in a minute, or check "
                    f"{self.base_url}."
                )
            raise

        if retry_response.status_code < 400:
            self._server_awake = True
        if self._is_wake_trigger(
            method, retry_safe=retry_safe, response=retry_response
        ):
            raise APIError(
                "Server did not wake up in time. Try again in a minute, or check "
                f"{self.base_url}."
            )
        return retry_response

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        retry_safe: bool = False,
    ) -> Dict[str, Any]:
        """Make HTTP request to API."""
        url = f"{self.base_url}{endpoint}"

        response = None
        try:
            response = self._http(
                method,
                url,
                retry_safe=retry_safe,
                headers=self._headers(),
                params=params,
                json=json,
                timeout=30,
                verify=self._verify,
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
            except (json.JSONDecodeError, ValueError, KeyError):
                raise APIError(f"API error: {e}")
        except requests.exceptions.RequestException as e:
            # Keep network errors readable; urllib3 can be very verbose.
            host = None
            try:
                from urllib.parse import urlparse

                host = urlparse(url).hostname
            except (ValueError, AttributeError):
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

    def _delete_no_content(self, endpoint: str, *, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Delete an endpoint which normally returns HTTP 204 No Content."""
        url = f"{self.base_url}{endpoint}"
        response = None
        try:
            response = self._http(
                "DELETE",
                url,
                retry_safe=True,
                headers=self._headers(),
                json=data,
                timeout=30,
                verify=self._verify,
            )
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return {"ok": True}
            return response.json()
        except requests.exceptions.HTTPError as e:
            try:
                error_data = response.json() if response is not None else {}
                error_msg = error_data.get("error", str(e))
                raise APIError(f"API error: {error_msg}")
            except APIError:
                raise
            except (json.JSONDecodeError, ValueError, KeyError):
                raise APIError(f"API error: {e}")

    def get_token_with_password(self, username_or_email: str, password: str) -> str:
        """Fetch an auth token using username/email + password.

        Uses DRF's built-in token endpoint at /get-auth-token/.
        """
        url = f"{self.base_url}/get-auth-token/"
        resp = self._http(
            "POST",
            url,
            json={"username": username_or_email, "password": password},
            headers={"Accept": "application/json"},
            timeout=30,
            verify=self._verify,
        )
        if resp.status_code >= 400:
            try:
                data = resp.json()
                detail = data.get("detail") or data.get("error") or str(data)
            except (json.JSONDecodeError, ValueError):
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

    def get_cached_me(
        self, *, ttl_seconds: int = 3600, refresh: bool = False
    ) -> Dict[str, Any]:
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
        except (OSError, IOError):
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
            "last_session_minutes": float|None,  # duration of last session
            "today_project": str|None,  # last from today if any
            "most_frequent_project": str|None,  # most sessions in lookback
            "streak_days": int,  # consecutive days with sessions
          }

        Cached to avoid frequent API calls.
        """
        from .utils.recent_activity_cache import (
            load_cached_activity,
            save_cached_activity,
        )

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
        last_session_minutes = None
        today_project = None
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
                except (AttributeError, IndexError):
                    pass

            # Overall last
            if last_end is None and end:
                last_end = end
                last_project = p
                # Capture the last session's duration
                try:
                    last_session_minutes = float(dur) if dur is not None else None
                except (ValueError, TypeError):
                    last_session_minutes = None

            # Today's last
            if today_project is None and end and end.startswith(today_str):
                today_project = p

        # Most frequent project
        most_frequent_project = (
            project_counts.most_common(1)[0][0] if project_counts else None
        )

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
            "last_session_minutes": last_session_minutes,
            "today_project": today_project,
            "most_frequent_project": most_frequent_project,
            "streak_days": streak_days,
        }

        try:
            save_cached_activity(info)
        except (OSError, IOError):
            pass

        return {**info, "cached": False}

    # Timer endpoints

    def start_timer(
        self,
        project: str,
        subprojects: Optional[List[str]] = None,
        note: Optional[str] = None,
        stop_after: Optional[Any] = None,
    ) -> Dict:
        """Start a new timer."""
        start = datetime.now(timezone.utc).isoformat()
        data = {"project": project, "start": start}
        if subprojects:
            data["subprojects"] = subprojects
        if note:
            data["note"] = note
        if stop_after is not None:
            data["stop_after"] = stop_after
        return self._request("POST", "/api/timer/start/", json=data)

    def stop_timer(
        self,
        session_id: Optional[int] = None,
        project: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Dict:
        """Stop the current timer."""
        end = datetime.now(timezone.utc).isoformat()
        data = {"end": end}
        if session_id:
            data["session_id"] = session_id
        if project:
            data["project"] = project
        if note is not None:
            data["note"] = note
        return self._request(
            "POST", "/api/timer/stop/", json=data, retry_safe=True
        )

    def get_timer_status(
        self, session_id: Optional[int] = None, project: Optional[str] = None
    ) -> Dict:
        """Get status of active timer(s)."""
        params = {}
        if session_id:
            params["session_id"] = session_id
        if project:
            params["project"] = project
        return self._request("GET", "/api/timer/status/", params=params)

    def restart_timer(
        self, session_id: Optional[int] = None, project: Optional[str] = None
    ) -> Dict:
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
        return self._request(
            "DELETE", "/api/timer/delete/", params=params, retry_safe=True
        )

    # Session endpoints

    def log_activity(
        self,
        period: Optional[str] = None,
        project: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
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
        if exclude:
            params["exclude"] = ",".join(exclude)
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
        exclude: Optional[List[str]] = None,
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
        if exclude:
            params["exclude"] = ",".join(exclude)

        params["compact"] = "false" # make sure to get full session data and session notes

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
        exclude: Optional[List[str]] = None,
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
        if exclude:
            params["exclude"] = ",".join(exclude)
        return self._request("GET", "/api/projects/grouped/", params=params)

    def create_project(
        self,
        name: str,
        description: Optional[str] = None,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict:
        """Create a new project."""
        data = {"name": name}
        if description:
            data["description"] = description
        if context is not None:
            data["context"] = context
        if tags is not None:
            data["tags"] = tags
        return self._request("POST", "/api/create_project/", json=data)

    def update_project_metadata(
        self,
        project: str,
        *,
        description: Any = _UNSET,
        context: Any = _UNSET,
        tags: Any = _UNSET,
    ) -> Dict:
        """Update a project's description, context, and/or complete tag set."""
        data: Dict[str, Any] = {"project": project}
        if description is not _UNSET:
            data["description"] = description
        if context is not _UNSET:
            data["context"] = context
        if tags is not _UNSET:
            data["tags"] = tags
        return self._request("PATCH", "/api/project/update/", json=data)

    def list_subprojects(self, project: str, compact: bool = True) -> Dict:
        """List subprojects for a project."""
        params = {"project": project, "compact": str(compact).lower()}
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
        return self._request(
            "GET", "/api/tally_by_sessions/", params=params
        )

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
        exclude: Optional[List[str]] = None,
    ) -> List[Dict]:
        """List sessions (for charts)."""
        params = {"compact": "false"}
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
        if exclude:
            params["exclude"] = ",".join(exclude)
        return self._request("GET", "/api/list_sessions/", params=params)

    def list_contexts(self, compact: bool = True) -> Dict:
        """List available contexts for the authenticated user."""
        params = {"compact": str(compact).lower()}
        return self._request("GET", "/api/contexts/", params=params)

    def list_tags(self, compact: bool = True) -> Dict:
        """List available tags for the authenticated user."""
        params = {"compact": str(compact).lower()}
        return self._request("GET", "/api/tags/", params=params)

    # Context and tag management

    def create_context(self, name: str, description: Optional[str] = None) -> Dict:
        """Create a context."""
        data: Dict[str, Any] = {"name": name}
        if description is not None:
            data["description"] = description
        return self._request("POST", "/api/contexts/", json=data)

    def update_context(
        self, context_id: int, *, name: Any = _UNSET, description: Any = _UNSET
    ) -> Dict:
        """Update a context by ID."""
        data: Dict[str, Any] = {}
        if name is not _UNSET:
            data["name"] = name
        if description is not _UNSET:
            data["description"] = description
        return self._request("PATCH", f"/api/contexts/{context_id}/", json=data)

    def delete_context(self, context_id: int) -> Dict:
        """Delete a context by ID."""
        return self._delete_no_content(f"/api/contexts/{context_id}/")

    def create_tag(self, name: str, color: Optional[str] = None) -> Dict:
        """Create a tag."""
        data: Dict[str, Any] = {"name": name}
        if color is not None:
            data["color"] = color
        return self._request("POST", "/api/tags/", json=data)

    def update_tag(self, tag_id: int, *, name: Any = _UNSET, color: Any = _UNSET) -> Dict:
        """Update a tag by ID."""
        data: Dict[str, Any] = {}
        if name is not _UNSET:
            data["name"] = name
        if color is not _UNSET:
            data["color"] = color
        return self._request("PATCH", f"/api/tags/{tag_id}/", json=data)

    def delete_tag(self, tag_id: int) -> Dict:
        """Delete a tag by ID."""
        return self._delete_no_content(f"/api/tags/{tag_id}/")

    # Commitment endpoints

    def list_commitments(
        self,
        *,
        active: Optional[bool] = None,
        aggregation_type: Optional[str] = None,
        progress: bool = True,
        streak: bool = False,
        compact: bool = True,
    ) -> Dict:
        """List commitments, optionally filtering by active state or aggregation."""
        params: Dict[str, Any] = {
            "progress": str(progress).lower(),
            "streak": str(streak).lower(),
            "compact": str(compact).lower(),
        }
        if active is not None:
            params["active"] = str(active).lower()
        if aggregation_type:
            params["aggregation_type"] = aggregation_type
        return self._request("GET", "/api/commitments/", params=params)

    def get_commitment(self, commitment_id: int) -> Dict:
        """Get one commitment in its full representation."""
        return self._request("GET", f"/api/commitments/{commitment_id}/")

    def create_commitment(self, data: Dict[str, Any]) -> Dict:
        """Create a commitment from its API request fields."""
        return self._request("POST", "/api/commitments/", json=data)

    def update_commitment(self, commitment_id: int, data: Dict[str, Any]) -> Dict:
        """Patch the supplied commitment fields."""
        return self._request("PATCH", f"/api/commitments/{commitment_id}/", json=data)

    def delete_commitment(self, commitment_id: int) -> Dict:
        """Delete a commitment by ID."""
        return self._delete_no_content(f"/api/commitments/{commitment_id}/")

    def get_discovery_meta(
        self, *, ttl_seconds: int = 300, refresh: bool = False
    ) -> Dict[str, Any]:
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
        except (OSError, IOError):
            pass

        return {"contexts": contexts, "tags": tags, "cached": False}

    def get_discovery_projects(
        self, *, ttl_seconds: int = 300, refresh: bool = False
    ) -> Dict[str, Any]:
        """Get cached projects list for discovery/resolution.

        Returns: {"projects": [...], "cached": bool}

        Each project dict contains: name, description, status (active/paused/completed).
        This reduces repeated calls for commands that need to resolve project names.
        """
        from .utils.projects_cache import load_cached_projects, save_cached_projects

        if not refresh:
            snap = load_cached_projects(ttl_seconds=ttl_seconds)
            if snap is not None:
                return {"projects": snap.projects, "cached": True}

        # Fetch grouped projects and flatten into a single list with status attached
        grouped = self.list_projects_grouped()
        projects_by_status = grouped.get("projects", {})
        projects = []

        for status in ("active", "paused", "complete", "archived"):
            for proj in projects_by_status.get(status, []):
                proj_entry = {
                    "name": proj.get("name") or proj.get("project"),
                    "description": proj.get("description", ""),
                    "status": status,
                }
                projects.append(proj_entry)

        try:
            save_cached_projects(projects)
        except (OSError, IOError):
            pass

        return {"projects": projects, "cached": False}

    # Subproject management

    def create_subproject(
        self,
        parent_project: str,
        name: str,
        description: Optional[str] = None,
    ) -> Dict:
        """Create a new subproject under an existing project."""
        data = {"parent_project": parent_project, "name": name}
        if description:
            data["description"] = description
        return self._request("POST", "/api/create_subproject/", json=data)

    # Project status management

    def mark_project_status(self, project: str, status: str) -> Dict:
        """Mark a project with a new status (active, paused, complete, archived)."""
        data = {"project": project, "status": status}
        return self._request("POST", "/api/mark/", json=data)

    # Rename operations

    def rename_project(self, old_name: str, new_name: str) -> Dict:
        """Rename a project."""
        data = {"type": "project", "project": old_name, "new_name": new_name}
        return self._request("POST", "/api/rename/", json=data)

    def rename_subproject(
        self, project: str, old_subproject: str, new_subproject: str
    ) -> Dict:
        """Rename a subproject within a project."""
        data = {
            "type": "subproject",
            "project": project,
            "subproject": old_subproject,
            "new_name": new_subproject,
        }
        return self._request("POST", "/api/rename/", json=data)

    # Delete operations

    def delete_project(self, project: str) -> Dict:
        """Delete a project and all its sessions."""
        data = {"project": project}
        # This endpoint returns 204 No Content, so we handle it specially
        url = f"{self.base_url}/api/project/delete/"
        try:
            response = self._http(
                "DELETE",
                url,
                retry_safe=True,
                headers=self._headers(),
                json=data,
                timeout=30,
                verify=self._verify,
            )
            response.raise_for_status()
            # 204 returns no body
            if response.status_code == 204:
                return {"ok": True, "deleted": project}
            return response.json()
        except requests.exceptions.HTTPError as e:
            try:
                error_data = response.json() if response is not None else {}
                error_msg = error_data.get("error", str(e))
                raise APIError(f"API error: {error_msg}")
            except APIError:
                raise
            except (json.JSONDecodeError, ValueError, KeyError):
                raise APIError(f"API error: {e}")

    def delete_subproject(self, project: str, subproject: str) -> Dict:
        """Delete a subproject from a project."""
        from urllib.parse import quote

        endpoint = f"/api/delete_subproject/{quote(project, safe='')}/{quote(subproject, safe='')}/"
        # This endpoint likely returns 204 No Content
        url = f"{self.base_url}{endpoint}"
        try:
            response = self._http(
                "DELETE",
                url,
                retry_safe=True,
                headers=self._headers(),
                timeout=30,
                verify=self._verify,
            )
            response.raise_for_status()
            if response.status_code == 204:
                return {"ok": True, "deleted": subproject, "project": project}
            return response.json()
        except requests.exceptions.HTTPError as e:
            try:
                error_data = response.json() if response is not None else {}
                error_msg = error_data.get("error", str(e))
                raise APIError(f"API error: {error_msg}")
            except APIError:
                raise
            except (json.JSONDecodeError, ValueError, KeyError):
                raise APIError(f"API error: {e}")

    # Export

    def export_data(
        self,
        project: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        context: Optional[int] = None,
        tags: Optional[List[int]] = None,
        compress: bool = False,
        autumn_compatible: bool = True,
    ) -> Dict:
        """Export sessions/projects data as JSON.

        Note: context must be an integer ID, not a name.
        Tags should be a list of tag IDs.
        """
        data = {}
        if project:
            data["project_name"] = project
        if start_date:
            data["start_date"] = start_date
        if end_date:
            data["end_date"] = end_date
        if context is not None:
            data["context"] = context
        if tags:
            data["tags"] = tags
        if compress:
            data["compress"] = True
        if autumn_compatible:
            data["autumn_compatible"] = True
        return self._request("POST", "/api/export/", json=data)

    # Import

    def import_data(
        self,
        *,
        data: Optional[Dict[str, Any]] = None,
        data_compressed: Optional[str] = None,
        force: bool = False,
        merge: bool = False,
        tolerance: int = 2,
        autumn_import: bool = False,
        context: Optional[str] = None,
    ) -> Dict:
        """Import an export payload into the user's projects.

        Exactly one of ``data`` and ``data_compressed`` must be supplied.  The
        latter is the opaque string returned by a compressed export.
        """
        if (data is None) == (data_compressed is None):
            raise ValueError("Provide exactly one of data or data_compressed")

        payload: Dict[str, Any] = {
            "force": force,
            "merge": merge,
            "tolerance": tolerance,
            "autumn_import": autumn_import,
        }
        if data is not None:
            payload["data"] = data
        else:
            payload["data_compressed"] = data_compressed
        if context is not None:
            payload["context"] = context
        return self._request("POST", "/api/import/", json=payload)

    # Audit

    def audit_totals(self, dry_run: bool = False) -> Dict:
        """Recompute and persist totals for all projects and subprojects."""
        if dry_run:
            return self._request("POST", "/api/audit/", json={"dry_run": True})
        return self._request("POST", "/api/audit/")

    # Project details and search

    def get_project(self, name: str) -> Dict:
        """Get detailed information about a single project."""
        from urllib.parse import quote

        endpoint = f"/api/get_project/{quote(name, safe='')}/"
        return self._request("GET", endpoint)

    def search_projects(
        self, search_term: str, status: Optional[str] = None
    ) -> Dict:
        """Search projects by name with optional status filter."""
        params = {"search_term": search_term}
        if status:
            params["status"] = status
        return self._request("GET", "/api/search_projects/", params=params)

    def get_project_totals(
        self,
        project: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict:
        """Get project totals with subproject breakdown."""
        params = {"project": project, "compact": "true"}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if context:
            params["context"] = context
        if tags:
            params["tags"] = ",".join(tags)
        return self._request("GET", "/api/totals/", params=params)

    def search_subprojects(
        self, project: str, search_term: str
    ) -> Dict:
        """Search subprojects by name within a project."""
        params = {"project_name": project, "search_term": search_term}
        return self._request("GET", "/api/search_subprojects/", params=params)

    def merge_projects(
        self, project1: str, project2: str, new_project_name: str
    ) -> Dict:
        """Merge two projects into a new one."""
        data = {
            "project1": project1,
            "project2": project2,
            "new_project_name": new_project_name,
        }
        return self._request("POST", "/api/merge_projects/", json=data)

    def merge_subprojects(
        self, project_id: int, subproject1: str, subproject2: str, new_subproject_name: str
    ) -> Dict:
        """Merge two subprojects into a new one within a project."""
        data = {
            "project_id": project_id,
            "subproject1": subproject1,
            "subproject2": subproject2,
            "new_subproject_name": new_subproject_name,
        }
        return self._request("POST", "/api/merge_subprojects/", json=data)

    def list_projects_flat(
        self,
        status: Optional[str] = None,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search: Optional[str] = None,
        exclude: Optional[List[str]] = None,
        compact: bool = True,
    ) -> Dict:
        """List projects as a flat (ungrouped) list with optional filters."""
        params = {"compact": str(compact).lower()}
        if status:
            params["status"] = status
        if context:
            params["context"] = context
        if tags:
            params["tags"] = ",".join(tags)
        if search:
            params["search"] = search
        if exclude:
            params["exclude"] = ",".join(exclude)
        return self._request("GET", "/api/projects/", params=params)

    def edit_session(
        self,
        session_id: int,
        project: Optional[str] = None,
        subprojects: Optional[List[str]] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        note: Optional[str] = None,
        compact: bool = True,
    ) -> Dict:
        """Edit an existing completed session."""
        data = {}
        if project is not None:
            data["project"] = project
        if subprojects is not None:
            data["subprojects"] = subprojects
        if start is not None:
            data["start"] = start
        if end is not None:
            data["end"] = end
        if note is not None:
            data["note"] = note

        params = {"compact": str(compact).lower()}
        return self._request("PATCH", f"/api/session/{session_id}/", params=params, json=data)

    def delete_session(self, session_id: int) -> Dict:
        """Delete a completed/saved session by ID."""
        endpoint = f"/api/delete_session/{session_id}/"
        url = f"{self.base_url}{endpoint}"
        try:
            response = self._http(
                "DELETE",
                url,
                retry_safe=True,
                headers=self._headers(),
                timeout=30,
                verify=self._verify,
            )
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return {"ok": True, "deleted": session_id}
            return response.json()
        except requests.exceptions.HTTPError as e:
            try:
                error_data = response.json() if response is not None else {}
                error_msg = error_data.get("error", str(e))
                raise APIError(f"API error: {error_msg}")
            except APIError:
                raise
            except (json.JSONDecodeError, ValueError, KeyError):
                raise APIError(f"API error: {e}")

    # Chart data endpoints

    def tally_by_context(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict]:
        """Get time totals aggregated by context."""
        params = {}
        if start_date:
            params["start_date"] = self._chart_date_param(start_date)
        if end_date:
            params["end_date"] = self._chart_date_param(end_date)
        return self._request("GET", "/api/tally_by_context/", params=params)

    def tally_by_status(
        self,
        context: Optional[str] = None,
    ) -> List[Dict]:
        """Get project count and time totals by status."""
        params = {}
        if context:
            params["context"] = context
        return self._request("GET", "/api/tally_by_status/", params=params)

    def tally_by_tags(self) -> List[Dict]:
        """Get time and project count aggregated by tag."""
        return self._request("GET", "/api/tally_by_tags/")

    def get_hierarchy(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict:
        """Get nested Context → Project → Subproject hierarchy with time totals."""
        params = {}
        if start_date:
            params["start_date"] = self._chart_date_param(start_date)
        if end_date:
            params["end_date"] = self._chart_date_param(end_date)
        return self._request("GET", "/api/hierarchy/", params=params)

    def get_projects_with_stats(
        self,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Get projects with stats for radar chart visualization."""
        params = {}
        if context:
            params["context"] = context
        if tags:
            params["tags"] = ",".join(tags)
        return self._request("GET", "/api/projects_with_stats/", params=params)
