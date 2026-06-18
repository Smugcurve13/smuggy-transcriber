"""GUI-free transcription logic, shared by the CLI and the desktop app.

Kept free of any Qt/GUI imports so it can be unit-tested headlessly and
reused from both `transcribe.py` (CLI) and `app.py` (PySide6 GUI).
"""

import os

from groq import Groq, AuthenticationError, APIConnectionError

MODEL = "whisper-large-v3"

# Display label -> Whisper language code (None means auto-detect).
LANGUAGES = {
    "Auto-detect": None,
    "Hindi": "hi",
    "English": "en",
}

# Groq rejects uploads larger than 25 MB.
MAX_BYTES = 25 * 1024 * 1024


def validate_api_key(api_key):
    """Return one of "missing", "valid", "invalid", "network_error".

    Probes the Groq API cheaply with ``models.list()`` so we can tell an
    expired/revoked key ("invalid") apart from being offline
    ("network_error") — we never blame the key when the network is down.
    """
    if not api_key:
        return "missing"
    try:
        Groq(api_key=api_key).models.list()
        return "valid"
    except AuthenticationError:
        # 401 — covers expired, revoked, or disabled keys.
        return "invalid"
    except APIConnectionError:
        # Offline / DNS failure / timeout (APITimeoutError subclasses this).
        return "network_error"


def transcribe_audio(file_path, api_key, language=None):
    """Transcribe an audio file and return the transcript as text.

    ``language`` is a Whisper code like "hi"/"en", or None to auto-detect.
    """
    client = Groq(api_key=api_key)
    name = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        return client.audio.transcriptions.create(
            file=(name, f),
            model=MODEL,
            language=language or None,
            response_format="text",
        )
