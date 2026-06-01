# lib/settings.py — minimal best-effort JSON persistence for add-in state.
#
# Currently stores a single "first_run_done" flag so the palette can dock
# itself to the right on first launch and then defer to Fusion's native
# dock memory thereafter (issue #9). Kept deliberately tiny; all I/O is
# guarded so a read-only install never breaks the add-in.

import json
import os

_SETTINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "settings.json")


def load() -> dict:
    """Return the settings dict, or {} on any error."""
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save(data: dict) -> bool:
    """Write the settings dict. Returns True on success, False otherwise."""
    try:
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return True
    except Exception:
        return False
