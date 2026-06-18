"""SmuggyTranscriber — a dead-simple PySide6 desktop transcription app.

Run with ``python app.py``. On Windows it ships as a double-click
``Transcriber.exe`` built by GitHub Actions (see .github/workflows).
"""

import os
import sys

from dotenv import load_dotenv
from groq import AuthenticationError
from PySide6.QtCore import Qt, QThread, QObject, Signal, QUrl
from PySide6.QtGui import QGuiApplication, QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QStackedWidget,
    QScrollArea,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QPlainTextEdit,
    QFileDialog,
    QMessageBox,
)

import core
import settings

ORG = "SmuggyTranscriber"
APP_NAME = "Transcriber"
CONSOLE_URL = "https://console.groq.com"
AUDIO_FILTER = (
    "Audio files (*.mp3 *.wav *.m4a *.ogg *.webm *.mp4 *.flac);;All files (*)"
)


def resource_path(rel):
    """Resolve a bundled resource path, both in dev and in a PyInstaller exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


class TranscribeWorker(QObject):
    """Runs a transcription off the UI thread so the window never freezes."""

    finished = Signal(str)
    error = Signal(str)
    auth_error = Signal()  # 401 mid-use -> route back to setup

    def __init__(self, file_path, api_key, language):
        super().__init__()
        self._file_path = file_path
        self._api_key = api_key
        self._language = language

    def run(self):
        try:
            text = core.transcribe_audio(
                self._file_path, self._api_key, self._language
            )
            self.finished.emit(text)
        except AuthenticationError:
            self.auth_error.emit()
        except Exception as exc:  # surface anything else to the user verbatim
            self.error.emit(str(exc))


class SetupWidget(QWidget):
    """First-run / recovery screen: explain how to get a key and save it."""

    key_saved = Signal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.heading = QLabel()
        self.heading.setTextFormat(Qt.RichText)
        self.heading.setStyleSheet("font-size: 19px; font-weight: bold;")
        self.heading.setWordWrap(True)
        self.heading.setContentsMargins(30, 24, 30, 8)
        outer.addWidget(self.heading)

        # Scrollable instructions, with a screenshot under each step.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(30, 0, 30, 12)
        body.setSpacing(10)

        intro = QLabel(
            "To use SmuggyTranscriber you need your own free Groq API key. "
            "It only takes a minute:"
        )
        intro.setWordWrap(True)
        body.addWidget(intro)

        open_btn = QPushButton("Open Groq Console  (console.groq.com)")
        open_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(CONSOLE_URL))
        )
        body.addWidget(open_btn)

        self._add_step(body, "1.  Sign in (or create a free account).",
                       "step-1-signin.png")
        self._add_step(body, "2.  Open  API Keys , then click  Create API Key.",
                       "step-2-api-keys.png")
        self._add_step(body, "3.  Give it any name and click  Submit.",
                       "step-3-create-key.png")
        self._add_step(body, "4.  Copy the key — it starts with “gsk_” and is "
                             "shown only once.", "step-4-copy-key.png")
        self._add_step(body, "5.  Paste it in the box below, then "
                             "Save && Continue.")
        body.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        # Fixed footer: the key box + save button stay visible while scrolling.
        footer = QWidget()
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(30, 8, 30, 20)
        footer_layout.setSpacing(8)

        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("Paste your gsk_… key here")
        self.key_input.returnPressed.connect(self._save)
        footer_layout.addWidget(self.key_input)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #c0392b;")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        footer_layout.addWidget(self.error_label)

        self.save_btn = QPushButton("Save && Continue")
        self.save_btn.setMinimumHeight(40)
        self.save_btn.clicked.connect(self._save)
        footer_layout.addWidget(self.save_btn)

        outer.addWidget(footer)

    def _add_step(self, layout, text, image=None):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("font-weight: 600;")
        layout.addWidget(label)
        if image:
            pix = QPixmap(resource_path(os.path.join("assets", image)))
            if not pix.isNull():
                holder = QLabel()
                holder.setPixmap(
                    pix.scaledToWidth(420, Qt.SmoothTransformation)
                )
                layout.addWidget(holder)

    def set_reason(self, status):
        """Tailor the headline to why we're here."""
        if status == "invalid":
            self.heading.setText("⚠️  Your API key is invalid or expired")
        elif status == "reenter":
            self.heading.setText("Enter a new Groq API key")
        else:  # "missing"
            self.heading.setText("\U0001f44b  Welcome! Add your Groq API key to start")

    def _save(self):
        key = self.key_input.text().strip()
        if not key:
            self._show_error("Please paste your key first.")
            return

        self.save_btn.setEnabled(False)
        self.save_btn.setText("Checking…")
        QApplication.processEvents()
        status = core.validate_api_key(key)
        self.save_btn.setEnabled(True)
        self.save_btn.setText("Save && Continue")

        if status == "valid":
            settings.set_api_key(key)
            self.error_label.hide()
            self.key_input.clear()
            self.key_saved.emit()
        elif status == "invalid":
            self._show_error(
                "That key was rejected (invalid or expired). "
                "Double-check it and try again."
            )
        elif status == "network_error":
            self._show_error(
                "Couldn't reach Groq to verify the key. "
                "Check your internet connection and try again."
            )
        else:
            self._show_error("Please paste your key first.")

    def _show_error(self, msg):
        self.error_label.setText(msg)
        self.error_label.show()


class MainWidget(QWidget):
    """The main screen: choose a file, transcribe, copy/save the result."""

    reenter_key = Signal(str)

    def __init__(self):
        super().__init__()
        self._file_path = None
        self._thread = None
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(12)

        file_row = QHBoxLayout()
        self.choose_btn = QPushButton("Choose audio file…")
        self.choose_btn.clicked.connect(self._choose_file)
        file_row.addWidget(self.choose_btn)
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("color: #555;")
        file_row.addWidget(self.file_label, 1)
        layout.addLayout(file_row)

        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("Language:"))
        self.lang_combo = QComboBox()
        for label in core.LANGUAGES:
            self.lang_combo.addItem(label)
        lang_row.addWidget(self.lang_combo)
        lang_row.addStretch(1)
        self.key_btn = QPushButton("Re-enter API key")
        self.key_btn.clicked.connect(lambda: self.reenter_key.emit("reenter"))
        lang_row.addWidget(self.key_btn)
        layout.addLayout(lang_row)

        self.transcribe_btn = QPushButton("Transcribe")
        self.transcribe_btn.setMinimumHeight(46)
        self.transcribe_btn.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.transcribe_btn.clicked.connect(self._start)
        layout.addWidget(self.transcribe_btn)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #555;")
        layout.addWidget(self.status_label)

        self.result = QPlainTextEdit()
        self.result.setPlaceholderText("Your transcription will appear here.")
        layout.addWidget(self.result, 1)

        action_row = QHBoxLayout()
        self.copy_btn = QPushButton("Copy")
        self.copy_btn.clicked.connect(self._copy)
        self.save_btn = QPushButton("Save as .txt")
        self.save_btn.clicked.connect(self._save_txt)
        action_row.addWidget(self.copy_btn)
        action_row.addWidget(self.save_btn)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        self._set_results_enabled(False)

    def _set_results_enabled(self, on):
        self.copy_btn.setEnabled(on)
        self.save_btn.setEnabled(on)

    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose audio file", "", AUDIO_FILTER
        )
        if not path:
            return
        size = os.path.getsize(path)
        if size > core.MAX_BYTES:
            QMessageBox.warning(
                self,
                "File too large",
                f"That file is {size / (1024 * 1024):.1f} MB, but Groq's "
                "limit is 25 MB.\nPlease choose a smaller file, or trim/"
                "compress this one first.",
            )
            return
        self._file_path = path
        self.file_label.setText(os.path.basename(path))

    def _start(self):
        if not self._file_path:
            QMessageBox.information(self, "No file", "Choose an audio file first.")
            return

        api_key = settings.get_api_key()
        language = core.LANGUAGES[self.lang_combo.currentText()]

        self._set_busy(True)
        self.result.clear()
        self._set_results_enabled(False)
        self.status_label.setText("Transcribing… please wait.")

        self._thread = QThread()
        self._worker = TranscribeWorker(self._file_path, api_key, language)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.auth_error.connect(self._on_auth_error)
        # Tear the thread down once any terminal signal has fired.
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._worker.auth_error.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _set_busy(self, busy):
        self.transcribe_btn.setEnabled(not busy)
        self.choose_btn.setEnabled(not busy)
        if not busy:
            self.status_label.setText("")

    def _on_finished(self, text):
        self._set_busy(False)
        self.result.setPlainText(text)
        self._set_results_enabled(bool(text.strip()))

    def _on_error(self, msg):
        self._set_busy(False)
        QMessageBox.critical(self, "Transcription failed", msg)

    def _on_auth_error(self):
        self._set_busy(False)
        QMessageBox.warning(
            self,
            "API key rejected",
            "Your API key was rejected. Please enter a new one.",
        )
        self.reenter_key.emit("invalid")

    def _copy(self):
        QGuiApplication.clipboard().setText(self.result.toPlainText())
        self.status_label.setText("Copied to clipboard.")

    def _save_txt(self):
        default_name = "transcription.txt"
        if self._file_path:
            stem = os.path.splitext(os.path.basename(self._file_path))[0]
            default_name = f"{stem}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save transcription", default_name, "Text files (*.txt)"
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.result.toPlainText())
        self.status_label.setText(f"Saved to {os.path.basename(path)}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmuggyTranscriber")
        self.resize(660, 680)

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._setup = SetupWidget()
        self._main = MainWidget()
        self._stack.addWidget(self._setup)
        self._stack.addWidget(self._main)

        self._setup.key_saved.connect(self.show_main)
        self._main.reenter_key.connect(self.show_setup)

    def show_main(self):
        self._stack.setCurrentWidget(self._main)

    def show_setup(self, status="missing"):
        self._setup.set_reason(status)
        self._setup.key_input.clear()
        self._stack.setCurrentWidget(self._setup)


def _resolve_startup_screen(window):
    """Decide the first screen, handling the offline case interactively."""
    while True:
        status = core.validate_api_key(settings.get_api_key())
        if status == "valid":
            window.show_main()
            return
        if status in ("missing", "invalid"):
            window.show_setup(status)
            return

        # network_error: don't blame the key — let the user decide.
        box = QMessageBox(window)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Couldn't verify your key")
        box.setText("Couldn't verify your API key — you may be offline.")
        box.addButton("Retry", QMessageBox.AcceptRole)
        box.addButton("Continue anyway", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton().text() != "Retry":
            window.show_main()
            return


def main():
    load_dotenv()  # dev convenience: pick up GROQ_API_KEY from a local .env
    app = QApplication(sys.argv)
    app.setOrganizationName(ORG)
    app.setApplicationName(APP_NAME)

    window = MainWindow()
    _resolve_startup_screen(window)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
