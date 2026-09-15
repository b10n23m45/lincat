from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class UsageWindow:
    label: str
    used_percent: float
    remaining_percent: float
    reset_at: datetime | None
    window_minutes: int | None


@dataclass(frozen=True)
class CodexUsage:
    primary: UsageWindow | None
    secondary: UsageWindow | None
    plan_type: str | None
    has_credits: bool | None
    credit_balance: float | str | None
    source_file: Path | None
    observed_at: datetime
    source: str

    @property
    def used_percent(self) -> float:
        return self.primary.used_percent if self.primary else 0.0

    @property
    def remaining_percent(self) -> float:
        return self.primary.remaining_percent if self.primary else 0.0

    @property
    def reset_at(self) -> datetime | None:
        return self.primary.reset_at if self.primary else None

    @property
    def window_minutes(self) -> int | None:
        return self.primary.window_minutes if self.primary else None


def default_sessions_dir() -> Path:
    return Path.home() / ".codex" / "sessions"


def read_latest_usage(sessions_dir: Path | None = None) -> CodexUsage | None:
    """Read usage from the configured read API, then fall back to Codex JSONL records."""
    api_usage = read_usage_api()
    if api_usage is not None:
        return api_usage
    return read_local_session_usage(sessions_dir)


def read_usage_api() -> CodexUsage | None:
    url = os.environ.get("CODEX_USAGE_READ_API_URL")
    if not url:
        return None

    request = Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8")
    except (OSError, URLError):
        return None

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None

    rate_limits = _extract_rate_limits(data)
    if not rate_limits:
        return None
    timestamp = data.get("timestamp") if isinstance(data, dict) else None
    return _usage_from_rate_limits(rate_limits, None, _parse_timestamp(timestamp), "read-api")


def read_local_session_usage(sessions_dir: Path | None = None) -> CodexUsage | None:
    root = sessions_dir or default_sessions_dir()
    if not root.exists():
        return None

    latest: tuple[datetime, Path, dict[str, Any]] | None = None
    for path in root.rglob("*.jsonl"):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue

        for line in lines:
            if '"rate_limits"' not in line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            rate_limits = _extract_rate_limits(event)
            if not rate_limits:
                continue
            observed_at = _parse_timestamp(event.get("timestamp"))
            if latest is None or observed_at > latest[0]:
                latest = (observed_at, path, rate_limits)

    if latest is None:
        return None

    observed_at, source_file, rate_limits = latest
    return _usage_from_rate_limits(rate_limits, source_file, observed_at, "local-session")


def _extract_rate_limits(data: Any) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("rate_limits"), dict):
        return data["rate_limits"]
    payload = data.get("payload")
    if isinstance(payload, dict) and isinstance(payload.get("rate_limits"), dict):
        return payload["rate_limits"]
    return None


def _usage_from_rate_limits(
    rate_limits: dict[str, Any],
    source_file: Path | None,
    observed_at: datetime,
    source: str,
) -> CodexUsage:
    credits = rate_limits.get("credits") or {}
    return CodexUsage(
        primary=_window_from_limit("5 小時窗口", rate_limits.get("primary")),
        secondary=_window_from_limit("每週上限", rate_limits.get("secondary")),
        plan_type=rate_limits.get("plan_type"),
        has_credits=credits.get("has_credits"),
        credit_balance=credits.get("balance"),
        source_file=source_file,
        observed_at=observed_at,
        source=source,
    )


def _window_from_limit(label: str, limit: Any) -> UsageWindow | None:
    if not isinstance(limit, dict):
        return None
    used = float(limit.get("used_percent") or 0.0)
    return UsageWindow(
        label=label,
        used_percent=used,
        remaining_percent=max(0.0, 100.0 - used),
        reset_at=_from_unix(limit.get("resets_at")),
        window_minutes=limit.get("window_minutes"),
    )


def _parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _from_unix(value: int | float | str | None) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).astimezone()
    except (TypeError, ValueError, OSError):
        return None