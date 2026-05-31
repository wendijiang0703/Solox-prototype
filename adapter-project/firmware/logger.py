"""Persistent JSON log of travel entries on the MicroPython filesystem."""

import json
import os
import time
import machine

LOG_PATH = "log.json"


def _now_iso():
    y, mo, d, h, mi, s, _, _ = time.localtime()
    return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(y, mo, d, h, mi, s)


def _load():
    try:
        with open(LOG_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _save(entries):
    with open(LOG_PATH, "w") as f:
        json.dump(entries, f)


def all_entries():
    return _load()


def open_entry(env_reading, gps_reading):
    """Create and persist a new entry. Returns the entry dict."""
    entries = _load()
    entry = {
        "id": "entry_{:03d}".format(len(entries) + 1),
        "timestamp": _now_iso(),
        "location": gps_reading,
        "environment": env_reading,
        "duration_seconds": None,
        "_started_ms": time.ticks_ms(),
    }
    entries.append(entry)
    _save(entries)
    return entry


def close_entry(entry_id):
    """Mark an entry as closed by computing duration_seconds."""
    entries = _load()
    for e in entries:
        if e["id"] == entry_id and e.get("duration_seconds") is None:
            started = e.pop("_started_ms", None)
            if started is not None:
                e["duration_seconds"] = time.ticks_diff(time.ticks_ms(), started) // 1000
            break
    _save(entries)


def set_time_from_iso(iso_str):
    """Set the board RTC from an ISO 8601 string like '2026-05-30T22:17:30'.

    The board has no battery-backed clock, so the phone pushes its clock
    when the dashboard loads. Returns True on success.
    """
    try:
        date_part, time_part = iso_str.split("T")
        y, mo, d = (int(x) for x in date_part.split("-"))
        h, mi, s = (int(x) for x in time_part.split(":")[:3])
    except (ValueError, IndexError):
        return False
    if y < 2025:
        return False
    machine.RTC().datetime((y, mo, d, 0, h, mi, s, 0))
    return True


def restamp_recent_if_unset():
    """Re-stamp any entry whose timestamp looks wrong.

    "Wrong" = year outside 2025-2040 (catches both '2000-01-01' from an
    unset RTC and bad values like '2080' from corrupt GPS data on boot).
    Runs right after the phone syncs the clock.
    """
    entries = _load()
    changed = False
    now = _now_iso()
    for e in entries:
        ts = e.get("timestamp", "")
        try:
            year = int(ts[:4])
        except ValueError:
            continue
        if year < 2025 or year > 2040:
            e["timestamp"] = now
            changed = True
    if changed:
        _save(entries)
