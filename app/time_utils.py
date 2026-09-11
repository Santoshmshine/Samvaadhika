from datetime import datetime, timedelta, timezone
from statistics import median


IST = timezone(timedelta(hours=5, minutes=30), name="IST")
UTC = timezone.utc


def utc_to_ist(value: datetime | None) -> datetime | None:
    """Convert a stored naive UTC datetime to an IST-aware datetime."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(IST)


def format_ist(value: datetime | None, format_string: str) -> str:
    converted = utc_to_ist(value)
    return converted.strftime(format_string) if converted else "-"


def elapsed_seconds(started_at: datetime | None, ended_at: datetime | None = None) -> int | None:
    if started_at is None:
        return None
    ended_at = ended_at or datetime.utcnow()
    if started_at.tzinfo is not None and ended_at.tzinfo is None:
        ended_at = ended_at.replace(tzinfo=UTC)
    elif started_at.tzinfo is None and ended_at.tzinfo is not None:
        started_at = started_at.replace(tzinfo=UTC)
    return max(0, round((ended_at - started_at).total_seconds()))


def estimate_remaining_seconds(
    elapsed: int | None,
    progress: int,
    historical_durations: list[int | None] | None = None,
) -> int | None:
    if elapsed is None or progress <= 0 or progress >= 100:
        return None
    progress_estimate = elapsed * (100 - progress) / progress
    valid_history = [duration for duration in historical_durations or [] if duration is not None]
    historical_estimate = max(0, median(valid_history) - elapsed) if valid_history else 0
    return max(1, round(max(progress_estimate, historical_estimate)))


def format_duration(seconds: int | float | None) -> str:
    if seconds is None:
        return "-"
    total_seconds = max(0, round(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def format_duration_between(started_at: datetime | None, ended_at: datetime | None) -> str:
    return format_duration(elapsed_seconds(started_at, ended_at))