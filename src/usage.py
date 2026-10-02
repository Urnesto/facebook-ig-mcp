"""
Persistent usage log for the Instagram tools.

Every tracked action is appended to data/usage_<account>.json. The log is used to
enforce limits over a rolling window (it survives server restarts, unlike the
in-memory throttler) and to report what has been used.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# action -> (limit, window in hours)
Limits = Dict[str, Tuple[int, int]]


class UsageLimitError(Exception):
    """Raised when an action would exceed its configured limit."""


def _usage_path(account: str) -> Path:
    return DATA_DIR / f"usage_{account}.json"


def load_events(account: str) -> List[Dict[str, Any]]:
    path = _usage_path(account)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("events", [])


def record_event(account: str, action: str, **details: Any) -> None:
    events = load_events(account)
    events.append({"action": action, "at": datetime.utcnow().isoformat(), **details})
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _usage_path(account).write_text(
        json.dumps({"events": events}, indent=2), encoding="utf-8"
    )


def _count_recent(events: List[Dict[str, Any]], action: str, hours: int) -> int:
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    return sum(
        1
        for e in events
        if e["action"] == action and datetime.fromisoformat(e["at"]) >= cutoff
    )


def _window_label(hours: int) -> str:
    return "hour" if hours == 1 else f"{hours} hours"


def check_limit(account: str, action: str, limit: int, hours: int = 24) -> None:
    used = _count_recent(load_events(account), action, hours)
    if used >= limit:
        raise UsageLimitError(
            f"Limit reached: {used} of {limit} '{action}' actions used in the last "
            f"{_window_label(hours)}. Try again later or raise the limit in .env"
        )


def get_usage(account: str, limits: Limits) -> Dict[str, Any]:
    """Summarise usage against each limit and list every user already DMed."""
    events = load_events(account)

    quotas = {}
    for action, (limit, hours) in limits.items():
        used = _count_recent(events, action, hours)
        quotas[action] = {
            "used": used,
            "limit": limit,
            "remaining": max(limit - used, 0),
            "window": f"last {_window_label(hours)}",
        }

    by_day: Dict[str, Dict[str, int]] = {}
    dmed_users: Dict[str, Dict[str, Any]] = {}
    for e in events:
        day = by_day.setdefault(e["at"][:10], {})
        day[e["action"]] = day.get(e["action"], 0) + 1
        if e["action"] == "dm":
            user = dmed_users.setdefault(
                e["user_id"],
                {"user_id": e["user_id"], "username": e.get("username"), "times": 0},
            )
            user["username"] = e.get("username") or user["username"]
            user["times"] += 1
            user["last_sent_at"] = e["at"]
            user["last_message"] = e.get("message")

    return {
        "account": account,
        "quotas": quotas,
        "by_day": by_day,
        "dmed_users": list(dmed_users.values()),
    }
