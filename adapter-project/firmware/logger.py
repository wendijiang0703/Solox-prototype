"""Persistent JSON log of travel entries on the MicroPython filesystem."""

import json
import os
import time

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
