"""Jira REST API wrapper for SDL project metrics and service desk data."""

import os
import time
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("JIRA_BASE_URL", "https://your-instance.atlassian.net")
EMAIL = os.getenv("JIRA_EMAIL")
API_TOKEN = os.getenv("JIRA_API_TOKEN")
PROJECT = os.getenv("JIRA_PROJECT", "SDL")
REQUEST_TYPE_FIELD = os.getenv("JIRA_REQUEST_TYPE_FIELD", "customfield_10700")
CLOSED_STATUSES = [s.strip() for s in os.getenv("JIRA_CLOSED_STATUSES", "Fechado,Resolvido").split(",")]

auth = HTTPBasicAuth(EMAIL, API_TOKEN)
headers = {"Accept": "application/json", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class JiraClientError(Exception):
    """Base exception for Jira client errors."""


class JiraAuthError(JiraClientError):
    """Authentication/authorization failure."""


class JiraAPIError(JiraClientError):
    """Generic API error with optional HTTP status code."""

    def __init__(self, msg, status_code=None):
        super().__init__(msg)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Module-level cache object
# ---------------------------------------------------------------------------

class _Cache:
    def __init__(self):
        self._portal_groups = None
        self._priorities = None

    def clear(self):
        self._portal_groups = None
        self._priorities = None


_cache = _Cache()


# ---------------------------------------------------------------------------
# Internal HTTP helpers
# ---------------------------------------------------------------------------

def _request_with_retry(method: str, url: str, *, params=None, json_body=None, max_retries: int = 3):
    """Execute an HTTP request with exponential-backoff retry for transient failures.

    Args:
        method: HTTP method string ("GET" or "POST").
        url: Full request URL.
        params: Optional query-string parameters.
        json_body: Optional JSON body (for POST).
        max_retries: Total attempts before re-raising (default 3).

    Returns:
        Parsed JSON response as a Python object.

    Raises:
        JiraAuthError: On 401 or 403 responses.
        JiraAPIError: On other HTTP errors, timeouts, or connection failures.
    """
    backoff_seconds = [1, 2, 4]

    for attempt in range(max_retries):
        try:
            resp = requests.request(
                method,
                url,
                auth=auth,
                headers=headers,
                params=params,
                json=json_body,
                timeout=30,
            )
        except requests.exceptions.Timeout:
            exc = JiraAPIError("Request timeout", status_code=None)
            if attempt < max_retries - 1:
                time.sleep(backoff_seconds[attempt])
                continue
            raise exc
        except requests.exceptions.ConnectionError as e:
            exc = JiraAPIError(f"Connection error: {e}", status_code=None)
            if attempt < max_retries - 1:
                time.sleep(backoff_seconds[attempt])
                continue
            raise exc

        status = resp.status_code

        if status in (401, 403):
            raise JiraAuthError(
                f"Authentication/authorization failure (HTTP {status}) for {url}"
            )

        if status >= 400:
            # Retry 5xx on transient failures; do not retry 4xx
            if status >= 500 and attempt < max_retries - 1:
                time.sleep(backoff_seconds[attempt])
                continue
            raise JiraAPIError(
                f"HTTP {status} from {url}: {resp.text[:200]}",
                status_code=status,
            )

        return resp.json()

    # Should never reach here, but satisfy type checkers
    raise JiraAPIError("Exhausted retries")


def _get(url: str, params=None):
    """Perform a GET request with error handling and retry logic.

    Args:
        url: Full request URL.
        params: Optional query-string parameters.

    Returns:
        Parsed JSON response.
    """
    return _request_with_retry("GET", url, params=params)


def _post(url: str, body: dict) -> dict:
    """Perform a POST request with error handling and retry logic.

    Args:
        url: Full request URL.
        body: JSON-serialisable request body.

    Returns:
        Parsed JSON response.
    """
    return _request_with_retry("POST", url, json_body=body)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_issues(
    jql: str,
    fields: list[str],
    max_results: int = 100,
    next_page_token: str | None = None,
) -> dict:
    """Execute a JQL search via POST /rest/api/3/search/jql (cursor-based pagination).

    Args:
        jql: JQL query string.
        fields: List of Jira field IDs to include in the response.
        max_results: Page size (default 100).
        next_page_token: Opaque cursor returned by the previous page.

    Returns:
        Raw Jira search response dict containing ``issues`` and optionally
        ``nextPageToken``.
    """
    url = f"{BASE_URL}/rest/api/3/search/jql"
    body: dict = {
        "jql": jql,
        "fields": fields,
        "maxResults": max_results,
    }
    if next_page_token:
        body["nextPageToken"] = next_page_token
    return _post(url, body)


def search_all_issues(jql: str, fields: list[str]) -> list[dict]:
    """Paginate through all results using cursor-based pagination.

    Args:
        jql: JQL query string.
        fields: List of Jira field IDs to include in each issue.

    Returns:
        Flat list of all matching Jira issue dicts.
    """
    all_issues = []
    next_page_token = None
    page_size = 100

    while True:
        data = search_issues(jql, fields, max_results=page_size, next_page_token=next_page_token)
        issues = data.get("issues", [])
        all_issues.extend(issues)
        next_page_token = data.get("nextPageToken")
        if not issues or not next_page_token:
            break

    return all_issues


def get_portal_groups() -> dict[str, str]:
    """Return ``{group_id: group_name}`` for the SDL service desk portal groups (cached).

    Returns:
        Mapping of portal group IDs to their display names.  Returns an empty
        dict if the API call fails.
    """
    if _cache._portal_groups is not None:
        return _cache._portal_groups
    url = f"{BASE_URL}/rest/servicedeskapi/servicedesk/14/requesttypegroup"
    try:
        data = _get(url)
        groups = {}
        for grp in data.get("values", []):
            groups[str(grp["id"])] = grp["name"]
        _cache._portal_groups = groups
        return groups
    except Exception:
        _cache._portal_groups = {}
        return {}


def get_priorities() -> list[dict]:
    """Return priority list ordered by Jira criticality with colours (cached).

    Returns:
        List of dicts with ``name`` and ``color`` keys.  Returns an empty list
        if the API call fails.
    """
    if _cache._priorities is not None:
        return _cache._priorities
    url = f"{BASE_URL}/rest/api/3/priority"
    try:
        data = _get(url)
        priorities = [
            {"name": p.get("name", ""), "color": p.get("statusColor", "#94a3b8")}
            for p in data
        ]
        _cache._priorities = priorities
        return priorities
    except Exception:
        _cache._priorities = []
        return []


def get_metrics(
    period: str = "week",
    date_from: str | None = None,
    date_to: str | None = None,
    assignee: str | None = None,
) -> dict:
    """Return aggregated metrics for the SDL project.

    Priority: ``date_from``/``date_to`` > ``period`` shortcut.

    Args:
        period: One of ``"day"``, ``"week"``, or ``"month"`` (default ``"week"``).
        date_from: ISO date string (``YYYY-MM-DD``) for the start of the range.
        date_to: ISO date string (``YYYY-MM-DD``) for the end of the range.
        assignee: Display name to filter issues by assignee (optional).

    Returns:
        Dict with keys ``kpi``, ``by_category``, ``by_group``, ``by_assignee``,
        ``by_priority``, ``priority_meta``, ``by_day``, ``closed_by_day``, and
        ``csat``.
    """
    from datetime import datetime, timedelta, timezone

    if date_from and date_to:
        since = date_from
        until = date_to
    else:
        period_days = {"day": 1, "week": 7, "month": 30}
        days = period_days.get(period, 7)
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        until = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    assignee_clause = ""
    if assignee:
        safe = assignee.replace('"', '')
        assignee_clause = f' AND assignee = "{safe}"'

    jql_created = (
        f'project = {PROJECT}{assignee_clause}'
        f' AND created >= "{since}" AND created <= "{until}"'
        f' ORDER BY created ASC'
    )
    status_in = ", ".join(f'"{s}"' for s in CLOSED_STATUSES)
    status_not_in = status_in
    jql_resolved = (
        f'project = {PROJECT}{assignee_clause}'
        f' AND status in ({status_in})'
        f' AND updated >= "{since}" AND updated <= "{until}"'
        f' ORDER BY updated ASC'
    )
    jql_open = (
        f'project = {PROJECT}{assignee_clause}'
        f' AND status not in ({status_not_in})'
        f' AND created >= "{since}" AND created <= "{until}"'
        f' ORDER BY created DESC'
    )

    fields = [
        "issuetype", "status", "assignee", "priority",
        "created", "resolutiondate", "updated", "summary", REQUEST_TYPE_FIELD,
    ]

    created_issues = search_all_issues(jql_created, fields)
    resolved_issues = search_all_issues(jql_resolved, fields)
    open_issues = search_all_issues(jql_open, ["status", "created"])

    # Aggregations
    by_category: dict[str, int] = {}
    by_group_ids: dict[str, int] = {}
    by_assignee: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    by_day: dict[str, int] = {}
    resolution_days: list[float] = []

    for issue in created_issues:
        f = issue.get("fields", {})

        # Category from requestType
        request_type = (f.get(REQUEST_TYPE_FIELD) or {}).get("requestType") or {}
        category = request_type.get("name", "Sem categoria")
        by_category[category] = by_category.get(category, 0) + 1

        # Group from requestType.groupIds
        group_ids = request_type.get("groupIds") or []
        if group_ids:
            gid = str(group_ids[0])
            by_group_ids[gid] = by_group_ids.get(gid, 0) + 1

        assignee_field = f.get("assignee") or {}
        assignee_name = assignee_field.get("displayName", "Não atribuído")
        by_assignee[assignee_name] = by_assignee.get(assignee_name, 0) + 1

        priority = (f.get("priority") or {}).get("name", "Sem prioridade")
        by_priority[priority] = by_priority.get(priority, 0) + 1

        created_str = f.get("created") or ""
        if created_str:
            try:
                created_date = datetime.fromisoformat(created_str).strftime("%Y-%m-%d")
            except ValueError:
                created_date = created_str[:10]
            by_day[created_date] = by_day.get(created_date, 0) + 1

    for issue in resolved_issues:
        f = issue.get("fields", {})
        created_str = f.get("created", "")
        resolved_str = f.get("resolutiondate") or f.get("updated", "")
        if created_str and resolved_str:
            try:
                c = datetime.fromisoformat(created_str)
                r = datetime.fromisoformat(resolved_str)
                delta = (r - c).days
                if delta >= 0:
                    resolution_days.append(delta)
            except Exception:
                pass

    avg_resolution = round(sum(resolution_days) / len(resolution_days), 1) if resolution_days else 0
    csat = get_csat(since, until)

    # Map group IDs to names
    portal_groups = get_portal_groups()
    by_group = {
        portal_groups.get(gid, f"Grupo {gid}"): count
        for gid, count in by_group_ids.items()
    }

    sorted_days = sorted(by_day.items())
    priority_meta = get_priorities()

    return {
        "kpi": {
            "total_created": len(created_issues),
            "total_open": len(open_issues),
            "total_closed": len(resolved_issues),
            "avg_resolution_days": avg_resolution,
        },
        "by_category": by_category,
        "by_group": by_group,
        "by_assignee": by_assignee,
        "by_priority": by_priority,
        "priority_meta": priority_meta,
        "by_day": {d: c for d, c in sorted_days},
        "closed_by_day": _count_by_day(resolved_issues),
        "csat": csat,
    }


def _count_by_day(issues: list[dict]) -> dict[str, int]:
    """Count resolved issues by resolution date (``YYYY-MM-DD``).

    Args:
        issues: List of Jira issue dicts that include a ``resolutiondate`` field.

    Returns:
        Mapping of date strings to issue counts.
    """
    from datetime import datetime

    counts: dict[str, int] = {}
    for issue in issues:
        f = issue.get("fields", {})
        raw = f.get("resolutiondate") or f.get("updated") or ""
        if raw:
            try:
                date = datetime.fromisoformat(raw).strftime("%Y-%m-%d")
            except ValueError:
                date = raw[:10]
            counts[date] = counts.get(date, 0) + 1
    return counts


def get_csat(since: str, until: str) -> dict:
    """Fetch CSAT via JSM experimental feedback report endpoint.

    Args:
        since: Start date string (``YYYY-MM-DD``).
        until: End date string (``YYYY-MM-DD``).

    Returns:
        Dict with ``avg`` (float) and ``count`` (int).  Returns
        ``{"avg": 0, "count": 0}`` when data is unavailable.
    """
    url = f"{BASE_URL}/rest/servicedesk/1/projects/{PROJECT}/report/feedback/date-range"
    params = {"start": 1, "limit": 100, "expand": "overall", "startDate": since, "endDate": until}
    try:
        data = _get(url, params=params)
        summary = data.get("summary", {})
        avg = summary.get("average")
        count = summary.get("count")
        if avg is not None and count:
            return {"avg": round(float(avg), 1), "count": int(count)}
        # fallback: calculate from pagedResults if summary not present
        results = (data.get("pagedResults") or {}).get("results", [])
        if results:
            ratings = [float(v["rating"]) for v in results if v.get("rating")]
            if ratings:
                return {"avg": round(sum(ratings) / len(ratings), 1), "count": len(ratings)}
    except Exception:
        pass
    return {"avg": 0, "count": 0}


def get_csat_by_month() -> list[dict]:
    """Return CSAT avg and count for each of the last 6 months.

    Returns:
        List of dicts with keys ``label`` (e.g. ``"jan/25"``), ``avg``, and
        ``count``, ordered from oldest to most recent month.
    """
    from datetime import datetime, timezone
    from dateutil.relativedelta import relativedelta

    now = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_names = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    result = []

    for i in range(5, -1, -1):
        month_start = now - relativedelta(months=i)
        month_end = month_start + relativedelta(months=1) - relativedelta(days=1)
        first_day = month_start.strftime("%Y-%m-%d")
        last_day = month_end.strftime("%Y-%m-%d")
        label = f"{month_names[month_start.month - 1]}/{str(month_start.year)[2:]}"
        csat = get_csat(first_day, last_day)
        result.append({"label": label, "avg": csat["avg"], "count": csat["count"]})

    return result


def get_open_by_month() -> list[dict]:
    """Return count of currently-open issues grouped by creation month (last 6 months).

    Returns:
        List of dicts with keys ``month`` (``YYYY-MM``), ``label``, and
        ``count``, ordered from oldest to most recent month.
    """
    from datetime import datetime, timezone
    from dateutil.relativedelta import relativedelta

    jql = (
        f'project = {PROJECT} AND statusCategory != Done'
        f' AND created >= startOfMonth("-5") ORDER BY created ASC'
    )
    issues = search_all_issues(jql, ["created"])

    now = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_names = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

    months = []
    for i in range(5, -1, -1):
        month_start = now - relativedelta(months=i)
        months.append(month_start.strftime("%Y-%m"))

    counts = {m: 0 for m in months}
    for issue in issues:
        raw = (issue.get("fields", {}).get("created") or "")
        if raw:
            try:
                created_ym = datetime.fromisoformat(raw).strftime("%Y-%m")
            except ValueError:
                created_ym = raw[:7]
            if created_ym in counts:
                counts[created_ym] += 1

    result = []
    for m in months:
        year, mo = m.split("-")
        label = f"{month_names[int(mo) - 1]}/{year[2:]}"
        result.append({"month": m, "label": label, "count": counts[m]})
    return result


def get_assignees() -> list[str]:
    """Return sorted list of distinct assignee display names from the last 45 days.

    Returns:
        Alphabetically sorted list of assignee display names.
    """
    jql = (
        f'project = {PROJECT} AND assignee is not EMPTY'
        f' AND created >= "-45d" ORDER BY assignee ASC'
    )
    issues = search_all_issues(jql, ["assignee"])
    seen: set[str] = set()
    result: list[str] = []
    for issue in issues:
        assignee_field = issue.get("fields", {}).get("assignee") or {}
        name = assignee_field.get("displayName", "")
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return sorted(result)


def get_service_desk_id() -> str | None:
    """Return the service desk ID for the SDL project.

    Returns:
        Service desk ID string, or ``None`` if not found or on error.
    """
    url = f"{BASE_URL}/rest/servicedeskapi/servicedesk"
    try:
        data = _get(url)
        for sd in data.get("values", []):
            if sd.get("projectKey") == PROJECT:
                return str(sd["id"])
    except Exception:
        pass
    return None


def get_request_types(service_desk_id: str) -> list[dict]:
    """Fetch all request types for a given service desk.

    Args:
        service_desk_id: The numeric service desk ID string.

    Returns:
        List of request type dicts, or an empty list on error.
    """
    url = f"{BASE_URL}/rest/servicedeskapi/servicedesk/{service_desk_id}/requesttype"
    try:
        data = _get(url)
        return data.get("values", [])
    except Exception:
        return []
