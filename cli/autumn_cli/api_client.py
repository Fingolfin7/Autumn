"""API client for communicating with AutumnWeb API."""

import json
import time
import requests
from datetime import datetime, timedelta, timezone
from json import JSONDecodeError
from typing import Optional, Dict, List, Any, Tuple
from uuid import uuid4
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
        self._project_id_cache: Dict[str, Tuple[float, int]] = {}
        self._subproject_id_cache: Dict[
            int, Tuple[float, List[Dict[str, Any]]]
        ] = {}

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
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to API."""
        url = f"{self.base_url}{endpoint}"
        request_headers = self._headers()
        if headers:
            request_headers.update(headers)

        response = None
        try:
            response = self._http(
                method,
                url,
                retry_safe=retry_safe,
                headers=request_headers,
                params=params,
                json=json,
                timeout=30,
                verify=self._verify,
            )
            response.raise_for_status()
            if endpoint.startswith("/api/v2/") and (
                response.status_code == 204 or not response.content
            ):
                return {}
            return response.json()
        except requests.exceptions.HTTPError as e:
            if endpoint.startswith("/api/v2/"):
                error_data = {}
                try:
                    error_data = response.json() if response is not None else {}
                except (JSONDecodeError, ValueError):
                    pass
                error_envelope = error_data.get("error")
                if isinstance(error_envelope, dict):
                    code = error_envelope.get("code")
                    message = error_envelope.get("message") or str(e)
                    if code == "version_conflict":
                        raise APIError(
                            "The timer changed on the server (someone else edited it?). "
                            "Re-run the command."
                        )
                    raise APIError(message)

            if response is not None and response.status_code == 401:
                raise APIError("Authentication failed. Check your API key.")
            try:
                error_data = response.json() if response is not None else {}
                error_msg = error_data.get("error", str(e))
                raise APIError(f"API error: {error_msg}")
            except APIError:
                raise
            except (JSONDecodeError, ValueError, KeyError):
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
        """Get the authenticated user's identity in the legacy v1 shape."""
        result = self._request("GET", "/api/v2/me/")
        user = result.get("user") or {}
        return {
            "ok": True,
            "id": user.get("id"),
            "username": user.get("username"),
            "email": user.get("email", ""),
            # v2 does not expose name fields; keep the stable legacy keys so
            # cached-user and account consumers need no special casing.
            "first_name": "",
            "last_name": "",
            "timezone": user.get("timezone"),
        }

    def get_cached_me(
        self, *, ttl_seconds: int = 3600, refresh: bool = False
    ) -> Dict[str, Any]:
        """Get cached v2 identity data for legacy greeting consumers."""
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

    @staticmethod
    def _session_v2_to_compact(resource: Dict[str, Any]) -> Dict[str, Any]:
        """Translate one v2 session resource to the v1 compact session shape."""
        project = resource.get("project") or {}
        allocations = resource.get("subproject_allocations") or []
        active = bool(resource.get("active"))
        elapsed = (
            resource.get("elapsed_minutes")
            if active
            else resource.get("duration_minutes")
        )
        return {
            "id": resource.get("id"),
            "p": project.get("name"),
            "pid": project.get("id"),
            "subs": [allocation.get("name") for allocation in allocations],
            "start": resource.get("start"),
            "end": resource.get("end"),
            "stop_at": resource.get("auto_stop_at"),
            "active": active,
            "elapsed": elapsed,
            "note": resource.get("note"),
        }

    @staticmethod
    def _session_v2_to_legacy(resource: Dict[str, Any]) -> Dict[str, Any]:
        """Translate one v2 session resource to the v1 full session shape."""
        project = resource.get("project") or {}
        allocations = resource.get("subproject_allocations") or []
        duration = resource.get("duration_minutes")
        if resource.get("active"):
            duration = resource.get("elapsed_minutes")
        return {
            "id": resource.get("id"),
            "project": project.get("name"),
            "subprojects": [
                allocation.get("name")
                for allocation in allocations
                if isinstance(allocation, dict)
            ],
            "start_time": resource.get("start"),
            "end_time": resource.get("end"),
            "duration_minutes": duration,
            "note": resource.get("note"),
        }

    def _v2_read_filter_params(
        self,
        *,
        project: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        note_snippet: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Translate the shared v1 read filters to v2 ID/date parameters."""
        params: Dict[str, Any] = {}
        if project:
            params["project_ids"] = str(self._resolve_project_id(project))
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        context_id, tag_ids = self._metadata_ids(context=context, tags=tags)
        if context_id is not None:
            params["context_ids"] = str(context_id)
        if tag_ids:
            params["tag_ids"] = ",".join(str(tag_id) for tag_id in tag_ids)
        if exclude:
            params["exclude_project_ids"] = ",".join(
                str(self._resolve_project_id(name)) for name in exclude
            )
        if note_snippet:
            params["note_snippet"] = note_snippet
        return params

    def _all_v2_session_resources(
        self,
        params: Optional[Dict[str, Any]] = None,
        *,
        page_size: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Fetch every v2 completed-session page from the requested offset."""
        resources: List[Dict[str, Any]] = []
        current_offset = offset
        base_params = dict(params or {})

        while True:
            page_params = {
                **base_params,
                "include": "note",
                "limit": page_size,
                "offset": current_offset,
            }
            page = self._request("GET", "/api/v2/sessions/", params=page_params)
            page_resources = list(page.get("sessions") or [])
            resources.extend(
                resource for resource in page_resources if isinstance(resource, dict)
            )
            total = int(page.get("total", current_offset + len(page_resources)))
            if not page_resources or current_offset + len(page_resources) >= total:
                break
            current_offset += len(page_resources)

        return resources

    @staticmethod
    def _to_utc_datetime(value: str) -> datetime:
        """Parse a supported v1 datetime value and return its UTC instant."""
        from .utils.datetime_parse import parse_user_datetime

        try:
            parsed = parse_user_datetime(value).dt
        except ValueError as original_error:
            parsed = None
            for date_format in ("%m-%d-%Y %H:%M:%S", "%m-%d-%Y"):
                try:
                    parsed = datetime.strptime(value, date_format)
                    break
                except ValueError:
                    continue
            if parsed is None:
                raise original_error
        return parsed.astimezone(timezone.utc)

    @classmethod
    def _to_utc_iso(cls, value: str) -> str:
        return cls._to_utc_datetime(value).isoformat()

    def _v2_projects(
        self, params: Optional[Dict[str, Any]] = None, *, page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch every page from the ordered v2 project collection."""
        projects: List[Dict[str, Any]] = []
        offset = 0
        base_params = dict(params or {})

        while True:
            page_params = {**base_params, "limit": page_size, "offset": offset}
            page = self._request("GET", "/api/v2/projects/", params=page_params)
            resources = list(page.get("projects") or [])
            projects.extend(
                resource for resource in resources if isinstance(resource, dict)
            )
            total = int(page.get("total", len(projects)))
            if not resources or len(projects) >= total:
                break
            offset += len(resources)

        return projects

    def _resolve_project_id(self, name: str, *, ttl_seconds: int = 300) -> int:
        """Resolve a project name through v2 search, caching exact matches briefly."""
        cache_key = name.casefold()
        now = time.monotonic()
        cached = self._project_id_cache.get(cache_key)
        if cached is not None and now - cached[0] <= ttl_seconds:
            return cached[1]

        candidates = self._v2_projects({"search": name})
        # An icontains search can return many similarly named projects. In that
        # case, scan the complete ordered collection before choosing an exact name.
        if len(candidates) > 1:
            candidates = self._v2_projects()

        folded_matches = [
            project
            for project in candidates
            if str(project.get("name") or "").casefold() == cache_key
        ]
        if len(folded_matches) > 1:
            case_matches = [
                project for project in folded_matches if project.get("name") == name
            ]
            if len(case_matches) == 1:
                folded_matches = case_matches
            else:
                raise APIError(f"Project name is ambiguous: {name}")

        if folded_matches:
            project_id = int(folded_matches[0]["id"])
            self._project_id_cache[cache_key] = (now, project_id)
            return project_id
        raise APIError(f"Project not found: {name}")

    def _get_subprojects_for_resolution(
        self, project: str, project_id: int, *, ttl_seconds: int = 300
    ) -> List[Dict[str, Any]]:
        now = time.monotonic()
        cached = self._subproject_id_cache.get(project_id)
        if cached is not None and now - cached[0] <= ttl_seconds:
            return cached[1]

        result = self._request("GET", f"/api/v2/projects/{project_id}")
        subprojects = result.get("subprojects", [])
        normalized = [sub for sub in subprojects if isinstance(sub, dict)]
        self._subproject_id_cache[project_id] = (now, normalized)
        return normalized

    def _resolve_subproject_ids(
        self, project: str, project_id: int, names: Optional[List[str]]
    ) -> Optional[List[int]]:
        if names is None:
            return None
        if not names:
            return []

        known = self._get_subprojects_for_resolution(project, project_id)
        ids_by_name = {}
        for sub in known:
            sub_name = sub.get("name") or sub.get("subproject")
            sub_id = sub.get("id") or sub.get("subproject_id")
            if sub_name and sub_id is not None:
                ids_by_name[str(sub_name)] = sub_id
        folded = {key.casefold(): value for key, value in ids_by_name.items()}
        missing = [name for name in names if name.casefold() not in folded]
        if missing:
            raise APIError(f"Unknown subprojects: {', '.join(missing)}")
        return [int(folded[name.casefold()]) for name in names]

    def _active_timer_resources(self) -> List[Dict[str, Any]]:
        result = self._request("GET", "/api/v2/timers/")
        return list(result.get("timers") or [])

    @staticmethod
    def _newest_timer(resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not resources:
            raise APIError("No active timer found.")

        def sort_key(resource: Dict[str, Any]) -> Tuple[datetime, int]:
            start = str(resource.get("start") or "")
            try:
                parsed = datetime.fromisoformat(start.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                parsed = datetime.min.replace(tzinfo=timezone.utc)
            return parsed, int(resource.get("id") or 0)

        return max(
            resources,
            key=sort_key,
        )

    def _resolve_active_timer_target(
        self, session_id: Optional[int], project: Optional[str]
    ) -> Dict[str, Any]:
        if session_id is not None:
            return self._request("GET", f"/api/v2/sessions/{session_id}")

        resources = self._active_timer_resources()
        if project is not None:
            matches = [
                resource
                for resource in resources
                if ((resource.get("project") or {}).get("name") or "").casefold()
                == project.casefold()
            ]
        else:
            matches = resources
        return self._newest_timer(matches)

    def start_timer(
        self,
        project: str,
        subprojects: Optional[List[str]] = None,
        note: Optional[str] = None,
        stop_after: Optional[Any] = None,
    ) -> Dict:
        """Start a new timer."""
        start = datetime.now(timezone.utc).isoformat()
        project_id = self._resolve_project_id(project)
        subproject_ids = self._resolve_subproject_ids(project, project_id, subprojects)
        data = {"project_id": project_id, "start": start, "uuid": str(uuid4())}
        if subproject_ids:
            data["subproject_ids"] = subproject_ids
        if note:
            data["note"] = note
        if stop_after is not None:
            data["stop_after_minutes"] = stop_after
        resource = self._request(
            "POST", "/api/v2/timers/", json=data, retry_safe=True
        )
        return {"ok": True, "session": self._session_v2_to_compact(resource)}

    def stop_timer(
        self,
        session_id: Optional[int] = None,
        project: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Dict:
        """Stop the current timer."""
        target = self._resolve_active_timer_target(session_id, project)
        end = datetime.now(timezone.utc).isoformat()
        data = {"end": end}
        if note is not None:
            data["note"] = note
        resource = self._request(
            "POST",
            f"/api/v2/timers/{target['id']}/stop/",
            json=data,
            retry_safe=True,
            headers={"If-Match": str(target["version"])},
        )
        compact = self._session_v2_to_compact(resource)
        return {"ok": True, "session": compact, "duration": compact["elapsed"]}

    def get_timer_status(
        self, session_id: Optional[int] = None, project: Optional[str] = None
    ) -> Dict:
        """Get status of active timer(s)."""
        resources = self._active_timer_resources()
        if session_id is not None:
            resources = [
                resource for resource in resources if resource.get("id") == session_id
            ]
        if project is not None:
            resources = [
                resource
                for resource in resources
                if ((resource.get("project") or {}).get("name") or "").casefold()
                == project.casefold()
            ]
        sessions = [
            self._session_v2_to_compact(resource) for resource in resources
        ]
        return {"ok": True, "active": len(sessions), "sessions": sessions}

    def restart_timer(
        self, session_id: Optional[int] = None, project: Optional[str] = None
    ) -> Dict:
        """Restart a timer."""
        target = self._resolve_active_timer_target(session_id, project)
        data = {"start": datetime.now(timezone.utc).isoformat()}
        resource = self._request(
            "POST",
            f"/api/v2/timers/{target['id']}/restart/",
            json=data,
            headers={"If-Match": str(target["version"])},
        )
        return {"ok": True, "session": self._session_v2_to_compact(resource)}

    def delete_timer(self, session_id: Optional[int] = None) -> Dict:
        """Delete a timer."""
        resources = self._active_timer_resources()
        matches = [
            resource for resource in resources if resource.get("id") == session_id
        ]
        if session_id is None:
            target = self._newest_timer(resources)
            target_id = target["id"]
        else:
            target = matches[0] if matches else None
            target_id = session_id
        headers = (
            {"If-Match": str(target["version"])} if target is not None else None
        )
        request_kwargs: Dict[str, Any] = {"retry_safe": True}
        if headers is not None:
            request_kwargs["headers"] = headers
        self._request("DELETE", f"/api/v2/timers/{target_id}", **request_kwargs)
        return {"ok": True, "deleted": target_id}

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
        if period and not start_date and not end_date:
            from .utils.periods import period_to_dates

            start_date, end_date = period_to_dates(period)
        params = self._v2_read_filter_params(
            project=project,
            start_date=start_date,
            end_date=end_date,
            context=context,
            tags=tags,
            exclude=exclude,
        )
        resources = self._all_v2_session_resources(params)
        logs = [self._session_v2_to_legacy(resource) for resource in resources]
        return {"count": len(logs), "logs": logs}

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
        params = self._v2_read_filter_params(
            project=project,
            start_date=start_date,
            end_date=end_date,
            context=context,
            tags=tags,
            exclude=exclude,
            note_snippet=note_snippet,
        )

        if active:
            result = self._request("GET", "/api/v2/timers/")
            resources = [
                resource
                for resource in result.get("timers") or []
                if isinstance(resource, dict)
            ]
            project_ids = {
                int(value)
                for value in str(params.get("project_ids", "")).split(",")
                if value
            }
            excluded_ids = {
                int(value)
                for value in str(params.get("exclude_project_ids", "")).split(",")
                if value
            }
            if project_ids:
                resources = [
                    resource
                    for resource in resources
                    if int((resource.get("project") or {}).get("id") or 0)
                    in project_ids
                ]
            if excluded_ids:
                resources = [
                    resource
                    for resource in resources
                    if int((resource.get("project") or {}).get("id") or 0)
                    not in excluded_ids
                ]
            if note_snippet:
                folded_note = note_snippet.casefold()
                resources = [
                    resource
                    for resource in resources
                    if folded_note in str(resource.get("note") or "").casefold()
                ]
            if offset:
                resources = resources[offset:]
            if limit:
                resources = resources[:limit]
        elif not limit:
            resources = self._all_v2_session_resources(params, offset=offset or 0)
        else:
            page_params = {**params, "include": "note", "limit": limit}
            if offset:
                page_params["offset"] = offset
            page = self._request("GET", "/api/v2/sessions/", params=page_params)
            resources = [
                resource
                for resource in page.get("sessions") or []
                if isinstance(resource, dict)
            ]

        sessions = [self._session_v2_to_legacy(resource) for resource in resources]
        return {"count": len(sessions), "sessions": sessions}

    def track_session(
        self,
        project: str,
        start: str,
        end: str,
        subprojects: Optional[List[str]] = None,
        note: Optional[str] = None,
    ) -> Dict:
        """Track a completed session."""
        project_id = self._resolve_project_id(project)
        subproject_ids = self._resolve_subproject_ids(
            project, project_id, subprojects
        )
        start_utc = self._to_utc_datetime(start)
        end_utc = self._to_utc_datetime(end)
        if end_utc < start_utc:
            start_utc -= timedelta(days=1)
        data = {
            "project_id": project_id,
            "start": start_utc.isoformat(),
            "end": end_utc.isoformat(),
            "uuid": str(uuid4()),
        }
        if subproject_ids:
            data["subproject_ids"] = subproject_ids
        if note:
            data["note"] = note
        resource = self._request(
            "POST", "/api/v2/sessions/", json=data, retry_safe=True
        )
        return {"ok": True, "session": self._session_v2_to_compact(resource)}

    # Project endpoints

    @staticmethod
    def _project_v2_to_legacy(resource: Dict[str, Any]) -> Dict[str, Any]:
        """Translate one v2 project resource to the full legacy project shape."""
        total_minutes = float(resource.get("total_minutes") or 0)
        session_count = int(resource.get("session_count") or 0)
        context = resource.get("context") or {}
        tags = resource.get("tags") or []
        return {
            "id": resource.get("id"),
            "name": resource.get("name"),
            "description": resource.get("description") or "",
            "status": resource.get("status"),
            "total_time": total_minutes,
            "total_minutes": total_minutes,
            "start_date": resource.get("start_date"),
            "last_updated": resource.get("last_activity"),
            "last_activity": resource.get("last_activity"),
            "session_count": session_count,
            "avg_session_duration": round(total_minutes / session_count, 2)
            if session_count
            else 0,
            "context": context.get("name"),
            "tags": [tag.get("name") for tag in tags if isinstance(tag, dict)],
        }

    @staticmethod
    def _subproject_v2_to_legacy(
        resource: Dict[str, Any], *, project_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Translate one v2 subproject resource to the legacy detail shape."""
        total_minutes = float(resource.get("total_minutes") or 0)
        session_count = int(resource.get("session_count") or 0)
        return {
            "id": resource.get("id"),
            "name": resource.get("name"),
            "description": resource.get("description") or "",
            "project_id": resource.get("project_id") or project_id,
            "total_time": total_minutes,
            "total_minutes": total_minutes,
            "last_updated": resource.get("last_activity"),
            "last_activity": resource.get("last_activity"),
            "session_count": session_count,
            "avg_session_duration": round(total_minutes / session_count, 2)
            if session_count
            else 0,
        }

    def _project_detail_v2_to_legacy(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        project = self._project_v2_to_legacy(resource)
        project["subprojects"] = [
            self._subproject_v2_to_legacy(
                subproject, project_id=resource.get("id")
            )
            for subproject in resource.get("subprojects") or []
            if isinstance(subproject, dict)
        ]
        return project

    @staticmethod
    def _days_since_project_activity(resource: Dict[str, Any]) -> int:
        """Derive the non-negative v1 radar recency value from v2 dates."""
        value = resource.get("last_activity") or resource.get("start_date")
        if not value:
            return 0
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return 0
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc).date() - parsed.date()).days)

    def _metadata_ids(
        self,
        *,
        context: Optional[Any] = None,
        tags: Optional[List[Any]] = None,
    ) -> Tuple[Optional[int], Optional[List[int]]]:
        """Resolve legacy context/tag names (or numeric strings) through cached metadata."""
        context_id: Optional[int] = None
        tag_ids: Optional[List[int]] = None
        needs_context_lookup = context is not None and not str(context).isdigit()
        needs_tag_lookup = tags is not None and any(
            not str(tag).isdigit() for tag in tags
        )
        meta = (
            self.get_discovery_meta(ttl_seconds=300, refresh=False)
            if needs_context_lookup or needs_tag_lookup
            else {"contexts": [], "tags": []}
        )

        if context is not None and str(context).casefold() != "all":
            if str(context).isdigit():
                context_id = int(context)
            else:
                match = next(
                    (
                        item
                        for item in meta.get("contexts", [])
                        if str(item.get("name") or "").casefold()
                        == str(context).casefold()
                    ),
                    None,
                )
                if not match or match.get("id") is None:
                    raise APIError(f"Unknown context: {context}")
                context_id = int(match["id"])

        if tags is not None:
            known_tags = {
                str(item.get("name") or "").casefold(): item.get("id")
                for item in meta.get("tags", [])
            }
            tag_ids = []
            missing = []
            for tag in tags:
                if str(tag).isdigit():
                    tag_ids.append(int(tag))
                    continue
                tag_id = known_tags.get(str(tag).casefold())
                if tag_id is None:
                    missing.append(str(tag))
                else:
                    tag_ids.append(int(tag_id))
            if missing:
                raise APIError(f"Unknown tags: {', '.join(missing)}")

        return context_id, tag_ids

    @staticmethod
    def _parse_window_date(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        for fmt in ("%Y-%m-%d", "%m-%d-%Y"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        raise APIError(f"Unrecognized date: {value!r} (use YYYY-MM-DD)")

    def _filter_project_window(
        self,
        resources: List[Dict[str, Any]],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Replicate v1's project date-window semantics client-side.

        v1 kept projects wholly contained in the window: start_date >= start
        AND last activity <= end + 1 day. A project with no completed
        sessions falls back to its start_date as its last activity.
        """
        start = self._parse_window_date(start_date)
        end = self._parse_window_date(end_date)
        if end is not None:
            end = end + timedelta(days=1)

        kept = []
        for resource in resources:
            project_start = self._parse_window_date(resource.get("start_date"))
            last_activity = self._parse_window_date(
                resource.get("last_activity") or resource.get("start_date")
            )
            if project_start is None:
                continue
            if start is not None and project_start < start:
                continue
            if end is not None and (last_activity is None or last_activity > end):
                continue
            kept.append(resource)
        return kept

    def list_projects_grouped(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
    ) -> Dict:
        """List v2 projects rebuilt into the full legacy grouped shape."""
        context_id, tag_ids = self._metadata_ids(context=context, tags=tags)
        params: Dict[str, Any] = {}
        if context_id is not None:
            params["context_ids"] = str(context_id)
        if tag_ids:
            params["tag_ids"] = ",".join(str(tag_id) for tag_id in tag_ids)
        if exclude:
            excluded_ids = [self._resolve_project_id(name) for name in exclude]
            params["exclude_project_ids"] = ",".join(
                str(project_id) for project_id in excluded_ids
            )

        resources = self._v2_projects(params)
        if start_date or end_date:
            resources = self._filter_project_window(resources, start_date, end_date)
        status_order = ("active", "paused", "complete", "archived")
        grouped: Dict[str, List[Dict[str, Any]]] = {
            status: [] for status in status_order
        }
        for resource in resources:
            status = str(resource.get("status") or "")
            grouped.setdefault(status, []).append(self._project_v2_to_legacy(resource))
        summary = {status: len(projects) for status, projects in grouped.items()}
        summary["total"] = len(resources)
        return {"summary": summary, "projects": grouped}

    def create_project(
        self,
        name: str,
        description: Optional[str] = None,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict:
        """Create a new project."""
        context_id, tag_ids = self._metadata_ids(context=context, tags=tags)
        data: Dict[str, Any] = {"name": name}
        if description:
            data["description"] = description
        if context_id is not None:
            data["context_id"] = context_id
        if tag_ids is not None:
            data["tag_ids"] = tag_ids
        resource = self._request("POST", "/api/v2/projects/", json=data)
        return self._project_v2_to_legacy(resource)

    def update_project_metadata(
        self,
        project: str,
        *,
        description: Any = _UNSET,
        status: Any = _UNSET,
        context: Any = _UNSET,
        tags: Any = _UNSET,
        start_date: Any = _UNSET,
    ) -> Dict:
        """Update project fields through v2 and return the legacy wrapper."""
        project_id = self._resolve_project_id(project)
        data: Dict[str, Any] = {}
        if description is not _UNSET:
            data["description"] = description
        if status is not _UNSET:
            data["status"] = status
        if context is not _UNSET:
            if context is None or context == "":
                context_id = None
            else:
                context_id, _ = self._metadata_ids(context=context)
            data["context_id"] = context_id
        if tags is not _UNSET:
            _, tag_ids = self._metadata_ids(tags=tags)
            data["tag_ids"] = tag_ids
        if start_date is not _UNSET:
            data["start_date"] = start_date
        resource = self._request(
            "PATCH", f"/api/v2/projects/{project_id}", json=data
        )
        return {"ok": True, "project": self._project_v2_to_legacy(resource)}

    def list_subprojects(self, project: str, compact: bool = True) -> Dict:
        """List v2 project-detail subprojects in the legacy list shape."""
        project_id = self._resolve_project_id(project)
        resource = self._request("GET", f"/api/v2/projects/{project_id}")
        subprojects = [
            subproject
            for subproject in resource.get("subprojects") or []
            if isinstance(subproject, dict)
        ]
        if compact:
            translated: List[Any] = [
                subproject.get("name") for subproject in subprojects
            ]
        else:
            translated = [
                self._subproject_v2_to_legacy(
                    subproject, project_id=project_id
                )
                for subproject in subprojects
            ]
        result = {
            "project": resource.get("name") or project,
            "subprojects": translated,
        }
        if not compact:
            result["project_id"] = project_id
        return result

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
        params = self._v2_read_filter_params(
            project=project_name,
            start_date=start_date,
            end_date=end_date,
            context=context,
            tags=tags,
        )
        result = self._request(
            "GET", "/api/v2/reports/tallies/", params={"by": "project", **params}
        )
        return [
            {"name": entry.get("name"), "total_time": entry.get("total_minutes")}
            for entry in result.get("entries") or []
            if isinstance(entry, dict)
        ]

    def tally_by_subprojects(
        self,
        project_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Get subproject totals (for charts)."""
        params = self._v2_read_filter_params(
            project=project_name,
            start_date=start_date,
            end_date=end_date,
            context=context,
            tags=tags,
        )
        result = self._request(
            "GET", "/api/v2/reports/tallies/", params={"by": "subproject", **params}
        )
        translated = []
        residual_total = 0
        for entry in result.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            if entry.get("kind") == "residual" or entry.get("name") is None:
                residual_total += entry.get("total_minutes") or 0
            else:
                translated.append(
                    {
                        "name": entry.get("name"),
                        "total_time": entry.get("total_minutes"),
                    }
                )
        if residual_total:
            translated.append({"name": "no subproject", "total_time": residual_total})
        return translated

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
        params = self._v2_read_filter_params(
            project=project_name,
            start_date=start_date,
            end_date=end_date,
            context=context,
            tags=tags,
            exclude=exclude,
        )
        return [
            self._session_v2_to_legacy(resource)
            for resource in self._all_v2_session_resources(params)
        ]

    def list_contexts(self, compact: bool = True) -> Dict:
        """List available contexts for the authenticated user."""
        result = self._request("GET", "/api/v2/contexts/")
        contexts = []
        for resource in result.get("contexts") or []:
            if not isinstance(resource, dict):
                continue
            context = {"id": resource.get("id"), "name": resource.get("name")}
            if not compact:
                context["project_count"] = resource.get("project_count", 0)
            contexts.append(context)
        return {"count": result.get("count", len(contexts)), "contexts": contexts}

    def list_tags(self, compact: bool = True) -> Dict:
        """List available tags for the authenticated user."""
        result = self._request("GET", "/api/v2/tags/")
        tags = []
        for resource in result.get("tags") or []:
            if not isinstance(resource, dict):
                continue
            tag = {"id": resource.get("id"), "name": resource.get("name")}
            if not compact:
                tag["project_count"] = resource.get("project_count", 0)
            tags.append(tag)
        return {"count": result.get("count", len(tags)), "tags": tags}

    # Context and tag management

    def create_context(self, name: str, description: Optional[str] = None) -> Dict:
        """Create a context."""
        data: Dict[str, Any] = {"name": name}
        if description is not None:
            data["description"] = description
        resource = self._request("POST", "/api/v2/contexts/", json=data)
        return {"ok": True, "context": resource}

    def update_context(
        self, context_id: int, *, name: Any = _UNSET, description: Any = _UNSET
    ) -> Dict:
        """Update a context by ID."""
        data: Dict[str, Any] = {}
        if name is not _UNSET:
            data["name"] = name
        if description is not _UNSET:
            data["description"] = description
        resource = self._request(
            "PATCH", f"/api/v2/contexts/{context_id}", json=data
        )
        return {"ok": True, "context": resource}

    def delete_context(self, context_id: int) -> Dict:
        """Delete a context by ID."""
        self._request(
            "DELETE", f"/api/v2/contexts/{context_id}", retry_safe=True
        )
        return {"ok": True}

    def create_tag(self, name: str, color: Optional[str] = None) -> Dict:
        """Create a tag."""
        data: Dict[str, Any] = {"name": name}
        if color is not None:
            data["color"] = color
        resource = self._request("POST", "/api/v2/tags/", json=data)
        return {"ok": True, "tag": resource}

    def update_tag(self, tag_id: int, *, name: Any = _UNSET, color: Any = _UNSET) -> Dict:
        """Update a tag by ID."""
        data: Dict[str, Any] = {}
        if name is not _UNSET:
            data["name"] = name
        if color is not _UNSET:
            data["color"] = color
        resource = self._request("PATCH", f"/api/v2/tags/{tag_id}", json=data)
        return {"ok": True, "tag": resource}

    def delete_tag(self, tag_id: int) -> Dict:
        """Delete a tag by ID."""
        self._request("DELETE", f"/api/v2/tags/{tag_id}", retry_safe=True)
        return {"ok": True}

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

        # Fetch the v2 grouped-equivalent façade and flatten its translated resources.
        grouped = self.list_projects_grouped()
        projects_by_status = grouped.get("projects", {})
        projects = []

        for status in ("active", "paused", "complete", "archived"):
            for proj in projects_by_status.get(status, []):
                proj_entry = dict(proj)
                proj_entry["status"] = status
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
        project_id = self._resolve_project_id(parent_project)
        data = {"name": name}
        if description:
            data["description"] = description
        resource = self._request(
            "POST", f"/api/v2/projects/{project_id}/subprojects/", json=data
        )
        return {"ok": True, "subproject": self._subproject_v2_to_legacy(resource)}

    # Project status management

    def mark_project_status(self, project: str, status: str) -> Dict:
        """Mark a project with a new status (active, paused, complete, archived)."""
        project_id = self._resolve_project_id(project)
        resource = self._request(
            "PATCH", f"/api/v2/projects/{project_id}", json={"status": status}
        )
        return {
            "ok": True,
            "project": resource.get("name"),
            "status": resource.get("status"),
        }

    # Rename operations

    def rename_project(self, old_name: str, new_name: str) -> Dict:
        """Rename a project."""
        project_id = self._resolve_project_id(old_name)
        resource = self._request(
            "PATCH", f"/api/v2/projects/{project_id}", json={"name": new_name}
        )
        return {"ok": True, "project": resource.get("name")}

    def rename_subproject(
        self, project: str, old_subproject: str, new_subproject: str
    ) -> Dict:
        """Rename a subproject within a project."""
        project_id = self._resolve_project_id(project)
        subproject_id = self._resolve_subproject_ids(
            project, project_id, [old_subproject]
        )[0]
        resource = self._request(
            "PATCH",
            f"/api/v2/subprojects/{subproject_id}",
            json={"name": new_subproject},
        )
        return {
            "ok": True,
            "project": project,
            "subproject": resource.get("name"),
        }

    # Delete operations

    def delete_project(self, project: str) -> Dict:
        """Delete a project and all its sessions."""
        project_id = self._resolve_project_id(project)
        self._request("DELETE", f"/api/v2/projects/{project_id}", retry_safe=True)
        return {"ok": True, "deleted": project}

    def delete_subproject(self, project: str, subproject: str) -> Dict:
        """Delete a subproject from a project."""
        project_id = self._resolve_project_id(project)
        subproject_id = self._resolve_subproject_ids(
            project, project_id, [subproject]
        )[0]
        self._request(
            "DELETE", f"/api/v2/subprojects/{subproject_id}", retry_safe=True
        )
        return {"ok": True, "deleted": subproject, "project": project}

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
        project_id = self._resolve_project_id(name)
        resource = self._request("GET", f"/api/v2/projects/{project_id}")
        return self._project_detail_v2_to_legacy(resource)

    def search_projects(
        self, search_term: str, status: Optional[str] = None
    ) -> Dict:
        """Search projects by name with optional status filter."""
        params = {"search": search_term}
        if status:
            params["status"] = status
        resources = self._v2_projects(params)
        return {
            "projects": [self._project_v2_to_legacy(resource) for resource in resources]
        }

    def get_project_totals(
        self,
        project: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict:
        """Get a project total in the legacy compact totals shape."""
        params = self._v2_read_filter_params(
            project=project,
            start_date=start_date,
            end_date=end_date,
            context=context,
            tags=tags,
        )
        result = self._request("GET", "/api/v2/reports/totals/", params=params)

        # The legacy totals shape carries a per-subproject breakdown; source it
        # from the v2 subproject tally (residual entries fold into the same
        # "no subproject" bucket the v1 endpoint used).
        tally_params = dict(params, by="subproject")
        tally = self._request(
            "GET", "/api/v2/reports/tallies/", params=tally_params
        )
        subs: List[List[Any]] = []
        residual_minutes = 0.0
        for entry in tally.get("entries", []):
            minutes = float(entry.get("total_minutes") or 0.0)
            if entry.get("kind") == "residual" or entry.get("name") is None:
                residual_minutes += minutes
            else:
                subs.append([entry["name"], minutes])
        if residual_minutes:
            subs.append(["no subproject", residual_minutes])

        return {
            "project": project,
            "total": result.get("total_minutes"),
            "subs": subs,
        }

    def search_subprojects(
        self, project: str, search_term: str
    ) -> List[Dict[str, Any]]:
        """Search project-detail subprojects with the legacy v1 semantics."""
        project_id = self._resolve_project_id(project)
        resource = self._request("GET", f"/api/v2/projects/{project_id}")
        subprojects = [
            subproject
            for subproject in resource.get("subprojects") or []
            if isinstance(subproject, dict)
        ]
        folded_term = search_term.casefold()
        matches = [
            subproject
            for subproject in subprojects
            if folded_term in str(subproject.get("name") or "").casefold()
        ]
        # v1 deliberately returned every subproject when a search had no hits.
        if not matches:
            matches = subprojects
        return [
            {
                **self._subproject_v2_to_legacy(
                    subproject, project_id=project_id
                ),
                "user": None,
                "parent_project": project_id,
                "start_date": None,
            }
            for subproject in matches
        ]

    def merge_projects(
        self, project1: str, project2: str, new_project_name: str
    ) -> Dict:
        """Merge two projects into a new one."""
        source_ids = [
            self._resolve_project_id(project1),
            self._resolve_project_id(project2),
        ]
        resource = self._request(
            "POST",
            "/api/v2/projects/merge/",
            json={"source_ids": source_ids, "new_name": new_project_name},
        )
        return {
            "message": (
                f"Successfully merged {project1} and {project2} into "
                f"{new_project_name}"
            ),
            "project": self._project_v2_to_legacy(resource),
        }

    def merge_subprojects(
        self, project_id: int, subproject1: str, subproject2: str, new_subproject_name: str
    ) -> Dict:
        """Merge two subprojects into a new one within a project."""
        source_ids = self._resolve_subproject_ids(
            "", project_id, [subproject1, subproject2]
        )
        resource = self._request(
            "POST",
            "/api/v2/subprojects/merge/",
            json={
                "project_id": project_id,
                "source_ids": source_ids,
                "new_name": new_subproject_name,
            },
        )
        return {
            "message": (
                f"Successfully merged {subproject1} and {subproject2} into "
                f"{new_subproject_name}"
            ),
            "subproject": self._subproject_v2_to_legacy(resource),
        }

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
        context_id, tag_ids = self._metadata_ids(context=context, tags=tags)
        params: Dict[str, Any] = {}
        if status:
            params["status"] = status
        if context_id is not None:
            params["context_ids"] = str(context_id)
        if tag_ids:
            params["tag_ids"] = ",".join(str(tag_id) for tag_id in tag_ids)
        if search:
            params["search"] = search
        if exclude:
            excluded_ids = [self._resolve_project_id(name) for name in exclude]
            params["exclude_project_ids"] = ",".join(
                str(project_id) for project_id in excluded_ids
            )
        resources = self._v2_projects(params)
        projects: List[Any]
        if compact:
            projects = [resource.get("name") for resource in resources]
        else:
            projects = [self._project_v2_to_legacy(resource) for resource in resources]
        return {"count": len(projects), "projects": projects}

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
        current = self._request("GET", f"/api/v2/sessions/{session_id}")
        current_project = current.get("project") or {}
        effective_project = project or current_project.get("name")
        if project is not None:
            project_id = self._resolve_project_id(project)
        else:
            project_id = current_project.get("id")

        data: Dict[str, Any] = {}
        if project is not None:
            data["project_id"] = project_id
        if subprojects is not None:
            data["subproject_ids"] = self._resolve_subproject_ids(
                effective_project, int(project_id), subprojects
            )
        if start is not None:
            data["start"] = self._to_utc_iso(start)
        if end is not None:
            data["end"] = self._to_utc_iso(end)
        if note is not None:
            data["note"] = note

        resource = self._request(
            "PATCH",
            f"/api/v2/sessions/{session_id}",
            json=data,
            headers={"If-Match": str(current["version"])},
        )
        return {"ok": True, "session": self._session_v2_to_compact(resource)}

    def delete_session(self, session_id: int) -> Dict:
        """Delete a completed/saved session by ID."""
        self._request(
            "DELETE", f"/api/v2/sessions/{session_id}", retry_safe=True
        )
        return {"ok": True, "deleted": session_id}

    # Chart data endpoints

    def tally_by_context(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict]:
        """Get time totals aggregated by context."""
        params = self._v2_read_filter_params(
            start_date=start_date,
            end_date=end_date,
        )
        result = self._request(
            "GET", "/api/v2/reports/tallies/", params={"by": "context", **params}
        )
        return [
            {"name": entry.get("name"), "total_time": entry.get("total_minutes")}
            for entry in result.get("entries") or []
            if isinstance(entry, dict)
        ]

    def tally_by_status(
        self,
        context: Optional[str] = None,
    ) -> List[Dict]:
        """Get project count and time totals by status."""
        params = self._v2_read_filter_params(context=context)
        result = self._request(
            "GET", "/api/v2/reports/tallies/", params={"by": "status", **params}
        )
        return [
            {"name": entry.get("name"), "total_time": entry.get("total_minutes")}
            for entry in result.get("entries") or []
            if isinstance(entry, dict)
        ]

    def tally_by_tags(self) -> List[Dict]:
        """Get time and project count aggregated by tag."""
        result = self._request(
            "GET", "/api/v2/reports/tallies/", params={"by": "tag"}
        )
        return [
            {"name": entry.get("name"), "total_time": entry.get("total_minutes")}
            for entry in result.get("entries") or []
            if isinstance(entry, dict)
        ]

    def get_hierarchy(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict:
        """Get nested Context → Project → Subproject hierarchy with time totals."""
        params = self._v2_read_filter_params(
            start_date=start_date,
            end_date=end_date,
        )
        result = self._request("GET", "/api/v2/reports/hierarchy/", params=params)
        projects = []
        for project in result.get("projects") or []:
            if not isinstance(project, dict):
                continue
            children = [
                {
                    "name": child.get("name"),
                    "subproject_id": child.get("id"),
                    "total_time": child.get("total_minutes"),
                }
                for child in project.get("children") or []
                if isinstance(child, dict) and child.get("kind") == "subproject"
            ]
            projects.append(
                {
                    "name": project.get("name"),
                    "project_id": project.get("id"),
                    "total_time": project.get("total_minutes"),
                    "children": children,
                }
            )
        return {
            "name": "All",
            "children": [{"name": "All", "context_id": None, "children": projects}],
        }

    def get_projects_with_stats(
        self,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Get v2 projects translated for the legacy radar-chart consumer."""
        context_id, tag_ids = self._metadata_ids(context=context, tags=tags)
        params: Dict[str, Any] = {}
        if context_id is not None:
            params["context_ids"] = str(context_id)
        if tag_ids:
            params["tag_ids"] = ",".join(str(tag_id) for tag_id in tag_ids)

        resources = self._v2_projects(params)
        translated = []
        for resource in resources:
            project_id = resource.get("id")
            subproject_count = resource.get("subproject_count")
            if subproject_count is None and project_id is not None:
                detail = self._request("GET", f"/api/v2/projects/{project_id}")
                subproject_count = len(detail.get("subprojects") or [])
            total_minutes = float(resource.get("total_minutes") or 0)
            translated.append(
                {
                    "name": resource.get("name"),
                    "total_time": total_minutes,
                    "computed_total_time": total_minutes,
                    "session_count": int(resource.get("session_count") or 0),
                    "subproject_count": int(subproject_count or 0),
                    "days_since_update": self._days_since_project_activity(resource),
                    "status": resource.get("status"),
                }
            )
        return translated
