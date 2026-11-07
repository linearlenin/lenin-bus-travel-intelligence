"""Formatting helpers for bus departure times."""

import re


def format_departure_time(value: object) -> str:
    """Convert 24-hour departure strings such as 23:45 to 11:45 PM."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""

    match = re.fullmatch(r"(?i)(\d{1,2}):(\d{2})\s*(am|pm)?", text)
    if not match:
        return text

    hour = int(match.group(1))
    minute = int(match.group(2))
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return text

    suffix = match.group(3).upper() if match.group(3) else ""
    if suffix:
        if suffix == "AM" and hour == 12:
            hour = 0
        elif suffix == "PM" and hour != 12:
            hour += 12
    else:
        suffix = "AM" if hour < 12 else "PM"

    display_hour = 12 if hour % 12 == 0 else hour % 12
    return f"{display_hour}:{minute:02d} {suffix}"
