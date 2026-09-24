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
    frame = frame.drop_duplicates(subset=["operator", "departure", "price_inr"]).reset_index(drop=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    frame.to_csv(CLEANED_PATH, index=False)
    print(f"Data pipeline complete: {len(frame)} records saved to {CLEANED_PATH}")
    return len(frame)


if __name__ == "__main__":
    run_pipeline()
