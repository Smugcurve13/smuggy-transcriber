import io
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

import core

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

load_dotenv()

AUDIO_FILE = Path(__file__).parent / "ReelAudio-39184.mp3"
OUTPUT_FILE = Path(__file__).parent / "transcription.txt"


def main():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY not found. Add it to your .env file.")
        sys.exit(1)

    if not AUDIO_FILE.exists():
        print(f"Error: Audio file not found at {AUDIO_FILE}")
        sys.exit(1)

    print(f"Transcribing {AUDIO_FILE.name} ...")
    text = core.transcribe_audio(str(AUDIO_FILE), api_key)

    print("\n--- Transcription ---")
    print(text)

    OUTPUT_FILE.write_text(text, encoding="utf-8")
    print(f"\nSaved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
