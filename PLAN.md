# Plan: SmuggyTranscriber — cross-platform desktop transcription app (PySide6 → Windows .exe)

> **This plan is portable.** It will be dropped into a brand-new repo named **`SmuggyTranscriber`** (a fresh folder), seeded with a copy of the existing `audio-to-text` script. Execute it from scratch in that folder — it does **not** depend on the original repo's branches or paths.

## Context

The starting point is a tiny CLI script (`transcribe.py`) that transcribes one hardcoded audio file via Groq's `whisper-large-v3` (`response_format="text"`, optional `language` hint like `"hi"`/`"en"`). The goal is a **dead-simple, double-clickable desktop app** for **non-technical, creative colleagues at a company, on Windows**, where a user can:

- Pick **any** audio file and see the transcription on screen, with **Copy** and **Save as .txt** buttons.
- On launch, have the app **sanity-check the Groq API key**, distinguishing **missing** vs **invalid/expired** (latter via a live API probe), plus a graceful **offline** case.
- When the key is missing/expired: see a clear message, a **short step-by-step to generate a new Groq key**, and an **input box to paste + save** their *own* key, then continue.

### Decisions (settled with the user)
- **GUI: PySide6 (Qt 6).** Cross-platform, the user knows it, `pip install pyside6` works on any machine (no `_tkinter`/Tk build needed), and it packages to a double-click `.exe`.
- **Primary target: a Windows double-click `Transcriber.exe`.** macOS is secondary (running `python app.py` is fine there).
- **Build/deliver: GitHub Actions.** A Windows runner builds the `.exe` and publishes it to the repo's Releases — no Windows machine needed to build.
- **Per-user key storage:** each colleague pastes their *own* Groq key on first run; stored per-user via `QSettings` (nothing committed, nothing to ship).
- **Language:** Whisper auto-detect with an optional selector (Auto / Hindi / English).

## Step 0 — New repo setup

1. Create the new GitHub repo **`SmuggyTranscriber`** and a local folder for it (the user is doing the copy step).
2. Seed it from the old project — copy in: `transcribe.py`, `requirements.txt`, `.env.example`, `README.md`, and (optional, for testing) a sample audio file such as `ReelAudio-39184.mp3`.
   - **Do not** copy: `venv/`, `.env` (secret), `__pycache__/`, `.DS_Store`.
3. `git init` (default branch `main`), add a `.gitignore` (`venv/`, `.env`, `__pycache__/`, `*.spec`, `build/`, `dist/`, `.DS_Store`).

## Architecture & files

### `core.py` — GUI-free logic (unit-testable, reused by CLI + GUI)
- `validate_api_key(api_key) -> status`, `status ∈ {"missing","valid","invalid","network_error"}`:
  - empty/`None` → `"missing"`; else probe cheaply via `Groq(api_key=...).models.list()`:
    - success → `"valid"`; `groq.AuthenticationError` (401) → `"invalid"` (covers expired/revoked/disabled); `groq.APIConnectionError`/timeout → `"network_error"` (don't blame the key when offline).
- `transcribe_audio(file_path, api_key, language=None) -> str`: wraps `client.audio.transcriptions.create(file=(name, f), model="whisper-large-v3", language=language or None, response_format="text")`.
- Constants: `MODEL`, `LANGUAGES = {"Auto-detect": None, "Hindi": "hi", "English": "en"}`, `MAX_BYTES = 25*1024*1024`.

### `settings.py` — per-user key storage
- `QSettings("SmuggyTranscriber", "Transcriber")` (Windows registry / macOS plist — real per-user store, nothing to ship).
- `get_api_key()`: saved key, falling back to env var `GROQ_API_KEY` (dev convenience).
- `set_api_key(key)`: persist via QSettings.

### `app.py` — PySide6 entry point
- `QApplication`; set org/app name so `QSettings` resolves; window title "SmuggyTranscriber".
- Startup: resolve key (`settings.get_api_key`) → `core.validate_api_key`:
  - `"valid"` → **MainWindow**; `"missing"`/`"invalid"` → **SetupWindow** (headline reflects which); `"network_error"` → small dialog "Couldn't verify your key (you may be offline)" with **Retry** / **Continue anyway**.
- **SetupWindow** (friendly, no jargon):
  - Heading: "⚠️ API key is **missing**" or "⚠️ API key is **invalid or expired**".
  - Numbered steps: (1) open https://console.groq.com & sign in, (2) click **API Keys**, (3) **Create API Key** → name → Submit, (4) copy the `gsk_…` key (shown once), (5) paste below. A button opens the console URL via `QDesktopServices.openUrl`.
  - Password-style `QLineEdit` + **Save & Continue**. On submit: re-validate; valid → `settings.set_api_key` → swap to MainWindow; else inline error + retry.
- **MainWindow** (one screen, big controls):
  - **Choose audio file…** → `QFileDialog` (mp3/wav/m4a/ogg/webm/mp4/flac); show picked name; reject > `MAX_BYTES` with a friendly note (Groq 25 MB limit).
  - **Language** `QComboBox` (Auto default).
  - Big **Transcribe** button → runs on a **QThread worker** (signals `finished(text)`/`error(msg)`) so the UI never freezes; show "Transcribing… please wait" + busy indicator.
  - Result in a `QPlainTextEdit`; **Copy** (`QGuiApplication.clipboard().setText`) and **Save as .txt** (`QFileDialog.getSaveFileName`, default `<audio-stem>.txt`).
  - A **re-enter API key** action (back to SetupWindow); a `401` mid-use routes back to setup too.

### `transcribe.py` — keep the CLI, refactor to import from `core.py` (no duplicated Groq logic).

## Packaging & delivery
- `requirements.txt`: `pyside6`, `groq`, `python-dotenv` (PyInstaller is build-only, installed in CI).
- **PyInstaller** one-file, windowed (no console): `pyinstaller --onefile --windowed --name Transcriber app.py` (add `--icon app.ico` if an icon is added; `--collect-all PySide6` if Qt-plugin hooks miss anything).
- **`.github/workflows/build-windows.yml`** (`runs-on: windows-latest`): checkout → setup-python → `pip install -r requirements.txt pyinstaller` → run PyInstaller → upload `dist/Transcriber.exe` as a workflow **artifact**, and attach to a **Release** on tag push (`v*`). Users download the `.exe` from Releases and double-click.
- Unsigned `.exe` triggers Windows **SmartScreen** ("More info → Run anyway") — fine for internal use; code signing is out of scope.

## README
Update `README.md` with **For users** (download `Transcriber.exe` from Releases → double-click → paste your own Groq key once → transcribe) and **For devs** (`pip install -r requirements.txt`, `python app.py`, how CI builds the exe).

## Verification
1. **Local (any OS, incl. this Mac):** `pip install pyside6 groq python-dotenv`, `python app.py`; confirm: no key → SetupWindow; paste real key → saved (QSettings) → MainWindow; junk key → "invalid/expired"; upload a sample mp3 → transcript shows; **Copy** + **Save as .txt** work; Hindi selector forces `language="hi"`.
2. **Headless:** test `core.validate_api_key` (real key → `valid`, `gsk_bad` → `invalid`) and `core.transcribe_audio` on a sample.
3. **CI:** push to GitHub → Actions builds → download `Transcriber.exe` artifact.
4. **Windows (user/colleague):** double-click `Transcriber.exe` → SetupWindow → paste own key → transcribe a file (dismiss SmartScreen via "More info → Run anyway").
