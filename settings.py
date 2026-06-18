"""Per-user Groq API key storage backed by QSettings.

QSettings writes to the real per-user store (Windows registry / macOS
plist) — so each colleague keeps their own key and nothing is ever
committed or shipped.
"""

import os

from PySide6.QtCore import QSettings

ORG = "SmuggyTranscriber"
APP = "Transcriber"

_KEY = "api_key"


def _settings():
    return QSettings(ORG, APP)


def get_api_key():
    """Return the saved key, falling back to the GROQ_API_KEY env var.

    The env-var fallback is a dev convenience (e.g. a local ``.env``); the
    saved value always wins once a user has pasted their own key.
    """
    saved = _settings().value(_KEY, "")
    if saved:
        return saved
    return os.getenv("GROQ_API_KEY", "")


def set_api_key(key):
    """Persist the API key for this user."""
    _settings().setValue(_KEY, key)
