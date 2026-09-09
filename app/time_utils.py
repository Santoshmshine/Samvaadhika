from datetime import datetime, timedelta, timezone


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