"""Normalize raw listings into filterable inventory features."""

import os
import re

import pandas as pd


DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
RAW_PATH = os.path.join(DATA_DIR, "bus_raw.csv")
CLEANED_PATH = os.path.join(DATA_DIR, "bus_cleaned.csv")


def _parse_price(value: object) -> int:
    digits = re.sub(r"[^\d]", "", str(value))
    if not digits:
        raise ValueError(f"Could not parse fare value: {value!r}")
    return int(digits)


def _parse_hour(value: object) -> int:
    match = re.match(r"^\s*(\d{1,2}):", str(value))
    if not match or int(match.group(1)) > 23:
        raise ValueError(f"Could not parse departure time: {value!r}")
    return int(match.group(1))


def _parse_duration(value: object) -> int:
    hours = re.search(r"(\d+)\s*h", str(value), re.IGNORECASE)
    minutes = re.search(r"(\d+)\s*m", str(value), re.IGNORECASE)
    return (int(hours.group(1)) * 60 if hours else 0) + (int(minutes.group(1)) if minutes else 0)


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


def run_pipeline() -> int:
    if not os.path.exists(RAW_PATH):
        raise FileNotFoundError(f"Source file {RAW_PATH} not found. Run scraper.py first.")
    frame = pd.read_csv(RAW_PATH)
    required = {"operator", "route", "departure", "duration", "seat_type", "price"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Raw inventory is missing columns: {sorted(missing)}")

    frame["price_inr"] = frame["price"].map(_parse_price)
    frame["departure_hour"] = frame["departure"].map(_parse_hour)
    frame["duration_mins"] = frame["duration"].map(_parse_duration)
    for column in ("operator", "route", "departure", "duration", "seat_type"):
        frame[column] = frame[column].astype(str).str.strip()
    frame["departure_display"] = frame["departure"].map(format_departure_time)
    frame = frame.drop_duplicates(subset=["operator", "departure", "price_inr"]).reset_index(drop=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    frame.to_csv(CLEANED_PATH, index=False)
    print(f"Data pipeline complete: {len(frame)} records saved to {CLEANED_PATH}")
    return len(frame)


if __name__ == "__main__":
    run_pipeline()
