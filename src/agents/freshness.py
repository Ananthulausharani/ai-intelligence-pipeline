"""
Reusable 24-Hour Freshness Utility for Phase II Pipeline Filtering.

Used by downstream ingestion agents (e.g. News and Job feeds) to filter
out stale or invalid records, ensuring only items published within the
last 24 hours are retained.
"""

import email.utils
from datetime import date, datetime, time, timezone
from typing import Any, Optional


def normalize_datetime(value: Any) -> Optional[datetime]:
    """
    Normalize an arbitrary date, datetime, or date string into a timezone-aware UTC datetime.

    Supported Formats:
    - datetime objects:
        * Naive datetimes are assumed to be in UTC.
        * Aware datetimes are converted to UTC via astimezone(timezone.utc).
    - date objects:
        * Normalized to UTC midnight (00:00:00 UTC) on that date.
    - ISO 8601 strings:
        * 'YYYY-MM-DDTHH:MM:SSZ'
        * 'YYYY-MM-DDTHH:MM:SS+HH:MM' / '-HH:MM'
        * 'YYYY-MM-DDTHH:MM:SS.ffffff'
    - Date-only strings ('YYYY-MM-DD'):
        * Normalized to UTC midnight (00:00:00 UTC) on that calendar date.
    - RFC 2822 / HTTP format strings (e.g. 'Fri, 11 Sep 2026 12:00:00 GMT'):
        * Parsed into timezone-aware UTC datetime.

    Returns:
        timezone-aware datetime with tzinfo=timezone.utc, or None if invalid/unparseable.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=timezone.utc)

    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None

        # 1. Try ISO-8601 parsing
        try:
            # Handle 'Z' suffix safely across all Python versions
            iso_str = s[:-1] + "+00:00" if s.endswith(("Z", "z")) else s
            dt = datetime.fromisoformat(iso_str)
            if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            pass

        # 2. Try RFC 2822 / HTTP header date format
        try:
            dt = email.utils.parsedate_to_datetime(s)
            if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass

    return None


def is_within_24_hours(
    published_at: Any,
    now: Optional[Any] = None,
) -> bool:
    """
    Determine whether a publication timestamp is strictly within the last 24 hours.

    Boundary & Normalization Rules:
    - Both published_at and now are normalized to timezone-aware UTC datetimes.
    - Exactly 24 hours old (delta == 24h) is INCLUDED (returns True).
    - Older than 24 hours (delta > 24h) is EXCLUDED (returns False).
    - Future timestamps (delta < 0s) are EXCLUDED (returns False).
    - Empty, missing, None, or unparseable timestamps return False.

    Args:
        published_at: The publication date/time (str, datetime, date).
        now: Optional reference time (defaults to datetime.now(timezone.utc) if None).

    Returns:
        True if 0 <= (now - published_at) <= 24 hours, False otherwise.
    """
    now_utc = normalize_datetime(now) if now is not None else datetime.now(timezone.utc)
    if now_utc is None:
        return False

    target_utc = normalize_datetime(published_at)
    if target_utc is None:
        return False

    delta = (now_utc - target_utc).total_seconds()

    # Reject future dates (delta < 0)
    if delta < 0:
        return False

    # 24 hours = 24 * 3600 = 86,400 seconds
    return delta <= 86400.0
