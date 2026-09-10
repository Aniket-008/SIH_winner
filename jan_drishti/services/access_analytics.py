"""Login and access analytics for the JAN-DRISHTI AI platform.

Answers the two questions an officer or administrator asks about the platform
itself: *how many people are signing in*, and *is anyone trying to break in*.

Everything is counted from data the platform already stores - the ``audit_log``
table (one row per sign-in attempt, written by the login handler) and the
``users`` / ``analysis_runs`` tables. Nothing is estimated or simulated.

Definitions used below (also shown in the UI so the numbers are never ambiguous):

* **login**        - an audit row with ``action = "LOGIN"`` and ``success = 1``.
* **failed login** - ``action = "LOGIN_FAILED"`` (wrong password) or
                     ``action = "AUTH_FAILED"`` (invalid/expired token).
* **active user**  - a user with a successful login inside the session lifetime
                     (8 hours), i.e. someone who could still be using the app.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Session lifetime used by AuthManager; kept here so "active users" matches the
# real token lifetime instead of a made-up window.
SESSION_HOURS = 8

LOGIN_ACTIONS = ("LOGIN",)
FAILED_ACTIONS = ("LOGIN_FAILED", "AUTH_FAILED")


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse the ISO timestamps stored by the database layer (tolerant)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _day_key(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d")


class AccessAnalytics:
    """Read-only analytics over the platform's own audit trail."""

    def __init__(self, db_manager: Any, now: Optional[datetime] = None) -> None:
        self.db = db_manager
        self._now = now

    # ------------------------------------------------------------------ #
    # helpers                                                             #
    # ------------------------------------------------------------------ #
    def _now_dt(self) -> datetime:
        return self._now or datetime.now()

    def _fetch_rows(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------ #
    # main entry point                                                    #
    # ------------------------------------------------------------------ #
    def summarize(
        self,
        days: int = 14,
        recent_limit: int = 15,
        include_ips: bool = False,
        user_admin: bool = False,
    ) -> Dict[str, Any]:
        """Build the complete login/access dashboard payload.

        ``include_ips`` controls whether the recent sign-in feed exposes client
        IP addresses. It is withheld unless the viewer is an administrator,
        mirroring the audit-log endpoint's permission model.
        """
        now = self._now_dt()
        days = max(1, min(int(days), 90))
        window_start = now - timedelta(days=days - 1)
        today = _day_key(now)
        active_cutoff = now - timedelta(hours=SESSION_HOURS)

        audit_rows = self._fetch_rows(
            "SELECT timestamp, user_id, username, action, details, ip_address, success "
            "FROM audit_log ORDER BY timestamp DESC"
        )
        users = self._fetch_rows(
            "SELECT user_id, username, role, full_name, email, created_at, last_login, is_active FROM users"
        )
        runs = self._fetch_rows(
            "SELECT run_id, username, uploaded_at, projects_analyzed, high_risk_count, critical_risk_count "
            "FROM analysis_runs ORDER BY uploaded_at DESC"
        )

        # ---- classify audit rows -------------------------------------
        logins: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []
        for row in audit_rows:
            action = (row.get("action") or "").upper()
            success = row.get("success", 1)
            if action in LOGIN_ACTIONS and success:
                logins.append(row)
            elif action in FAILED_ACTIONS or (action in LOGIN_ACTIONS and not success):
                failed.append(row)

        today_logins = [row for row in logins if (row.get("timestamp") or "").startswith(today)]
        today_failed = [row for row in failed if (row.get("timestamp") or "").startswith(today)]
        week_logins = [
            row for row in logins if (_parse_timestamp(row.get("timestamp")) or now) >= now - timedelta(days=7)
        ]

        total_attempts = len(logins) + len(failed)
        success_rate = round(len(logins) / total_attempts, 4) if total_attempts else 1.0

        # ---- daily series -------------------------------------------
        series: List[Dict[str, Any]] = []
        counts: Counter = Counter()
        failures: Counter = Counter()
        for row in logins:
            moment = _parse_timestamp(row.get("timestamp"))
            if moment and moment >= window_start:
                counts[_day_key(moment)] += 1
        for row in failed:
            moment = _parse_timestamp(row.get("timestamp"))
            if moment and moment >= window_start:
                failures[_day_key(moment)] += 1
        for offset in range(days):
            day = window_start + timedelta(days=offset)
            key = _day_key(day)
            series.append(
                {
                    "date": key,
                    "label": day.strftime("%d %b"),
                    "weekday": day.strftime("%a"),
                    "logins": counts.get(key, 0),
                    "failed": failures.get(key, 0),
                }
            )

        # ---- per-user view ------------------------------------------
        logins_per_user: Counter = Counter()
        failures_per_user: Counter = Counter()
        last_login_per_user: Dict[str, str] = {}
        last_attempt_per_user: Dict[str, str] = {}
        for row in logins:
            key = row.get("username") or row.get("user_id") or "unknown"
            logins_per_user[key] += 1
            stamp = row.get("timestamp")
            if stamp and (key not in last_login_per_user or stamp > last_login_per_user[key]):
                last_login_per_user[key] = stamp
        for row in failed:
            key = row.get("username") or row.get("user_id") or "unknown"
            failures_per_user[key] += 1
        for row in audit_rows:
            key = row.get("username") or ""
            stamp = row.get("timestamp")
            if key and stamp and (key not in last_attempt_per_user or stamp > last_attempt_per_user[key]):
                last_attempt_per_user[key] = stamp

        user_rows: List[Dict[str, Any]] = []
        for user in users:
            username = user.get("username") or user.get("user_id")
            last_login = last_login_per_user.get(username) or user.get("last_login")
            moment = _parse_timestamp(last_login)
            user_rows.append(
                {
                    "username": username,
                    "full_name": user.get("full_name") or "",
                    "role": user.get("role") or "",
                    "logins": logins_per_user.get(username, 0),
                    "failed_attempts": failures_per_user.get(username, 0),
                    "last_login": last_login,
                    "last_login_display": moment.strftime("%d %b %Y, %H:%M") if moment else "Never",
                    "active_now": bool(moment and moment >= active_cutoff),
                    "is_active": bool(user.get("is_active", 1)),
                    "never_logged_in": last_login is None,
                }
            )
        user_rows.sort(key=lambda item: (-item["logins"], item["username"] or ""))

        # ---- recent sign-in feed ------------------------------------
        recent: List[Dict[str, Any]] = []
        for row in sorted(audit_rows, key=lambda item: item.get("timestamp") or "", reverse=True):
            action = (row.get("action") or "").upper()
            if action not in LOGIN_ACTIONS and action not in FAILED_ACTIONS:
                continue
            moment = _parse_timestamp(row.get("timestamp"))
            entry = {
                "time": row.get("timestamp"),
                "time_display": moment.strftime("%d %b, %H:%M:%S") if moment else "-",
                "username": row.get("username") or "unknown",
                "action": action,
                "success": bool(row.get("success", 1)) and action in LOGIN_ACTIONS,
                "details": row.get("details") or "",
            }
            if include_ips:
                entry["ip_address"] = row.get("ip_address") or "-"
            recent.append(entry)
            if len(recent) >= recent_limit:
                break

        # ---- platform activity (the "traffic" side) ------------------
        today_runs = [row for row in runs if (row.get("uploaded_at") or "").startswith(today)]
        projects_screened = sum(int(row.get("projects_analyzed") or 0) for row in runs)
        active_users = [row for row in user_rows if row["active_now"]]

        return {
            "generated_at": now.isoformat(),
            "window": {"days": days, "from": _day_key(window_start), "to": today},
            "definitions": {
                "active_user": f"any user with a successful sign-in in the last {SESSION_HOURS} hours (the session lifetime)",
                "login": "an audit entry written every time a user signs in successfully",
                "failed_login": "wrong password (LOGIN_FAILED) or an invalid/expired token (AUTH_FAILED)",
            },
            "logins": {
                "total": len(logins),
                "today": len(today_logins),
                "last_7_days": len(week_logins),
                "in_window": sum(point["logins"] for point in series),
                "last_login_at": logins[0]["timestamp"] if logins else None,
                "last_login_user": (logins[0].get("username") if logins else None),
            },
            "failures": {
                "total": len(failed),
                "today": len(today_failed),
                "in_window": sum(point["failed"] for point in series),
                "success_rate": success_rate,
                "last_at": failed[0]["timestamp"] if failed else None,
            },
            "users": {
                "total": len(user_rows),
                "active_now": len(active_users),
                "logged_in_today": len({row["username"] for row in user_rows if row["last_login"] and row["last_login"].startswith(today)}),
                "never_logged_in": len([row for row in user_rows if row["never_logged_in"]]),
                "by_role": dict(Counter(row["role"] or "unknown" for row in user_rows)),
            },
            "activity": {
                "analyses_run": len(runs),
                "analyses_today": len(today_runs),
                "projects_screened": projects_screened,
                "last_analysis_at": runs[0]["uploaded_at"] if runs else None,
                "last_analysis_by": runs[0].get("username") if runs else None,
            },
            "series": series,
            "user_table": user_rows,
            "recent": recent,
            "ip_visible": bool(include_ips),
            "viewer_is_admin": bool(user_admin),
        }
