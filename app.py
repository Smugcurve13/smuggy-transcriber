"""SmuggyTranscriber — a dead-simple PySide6 desktop transcription app.

Green-on-black redesign: Space Grotesk + JetBrains Mono, bright-green accent.
Run with ``python app.py``; on Windows/macOS it ships as a packaged app built
by GitHub Actions (see .github/workflows/build.yml).
"""

import os
import sys

from dotenv import load_dotenv
from groq import AuthenticationError
from PySide6.QtCore import Qt, QThread, QObject, Signal, QUrl, QTimer
from PySide6.QtGui import QGuiApplication, QDesktopServices, QPixmap, QIcon, QFont
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QStackedWidget,
    QScrollArea,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QPlainTextEdit,
    QProgressBar,
    QFileDialog,
    QMessageBox,
    QSizePolicy,
)

import core
import settings
import theme
from theme import (
    font,
    label,
    SANS,
    MONO,
    ACCENT,
    ACCENT_HI,
    TEXT,
    TEXT_2,
    TEXT_3,
    MUTED,
    DISABLED,
    BORDER,
)

ORG = "SmuggyTranscriber"
APP_NAME = "Transcriber"
CONSOLE_URL = "https://console.groq.com"
AUDIO_FILTER = (
    "Audio files (*.mp3 *.wav *.m4a *.ogg *.webm *.mp4 *.flac);;All files (*)"
)

# Solid blends of the accent over the dark surfaces (avoids rgba-alpha quirks).
TINT_NUM = "#16301f"     # numbered step circles
TINT_DROP = "#14231a"    # drop-zone icon circle
TINT_BADGE = "#172e20"   # language badge
TINT_BORDER = "#244a31"


def resource_path(rel):
    """Resolve a bundled resource path, both in dev and in a packaged app."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def app_version():
    """Single source of truth for the version — read from the VERSION file."""
    try:
        with open(resource_path("VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "0.0.0"


def _accent_dot(size=9):
    dot = QLabel()
    dot.setFixedSize(size, size)
    dot.setStyleSheet(f"background: {ACCENT}; border-radius: {size // 2}px;")
    return dot


def _circle_number(n):
    lbl = QLabel(str(n))
    lbl.setFixedSize(24, 24)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setFont(font(MONO, 12, QFont.DemiBold))
    lbl.setStyleSheet(
        f"background: {TINT_NUM}; color: {ACCENT_HI}; border-radius: 12px;"
    )
    return lbl


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


class RomaniseWorker(QObject):
    """Transliterates Devanagari to Hinglish off the UI thread."""

    finished = Signal(str)
    error = Signal(str)

    def __init__(self, text, api_key):
        super().__init__()
        self._text = text
        self._api_key = api_key

    def run(self):
        try:
            self.finished.emit(core.romanise_hindi(self._text, self._api_key))
        except Exception as exc:
            self.error.emit(str(exc))


class SetupWidget(QWidget):
    """First-run / recovery screen: explain how to get a key and save it."""

    key_saved = Signal()

    def __init__(self):
        super().__init__()
        self._step_images = []  # (label, full-res pixmap) for responsive scaling

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Brand header: logo + name + tagline.
        header = QHBoxLayout()
        header.setContentsMargins(28, 26, 28, 4)
        header.setSpacing(14)
        logo = QLabel()
        logo.setFixedSize(52, 52)
        logo.setScaledContents(True)
        logo.setPixmap(QPixmap(theme.logo_path()))
        header.addWidget(logo)
        brand = QVBoxLayout()
        brand.setSpacing(2)
        brand.addWidget(label("SmuggyTranscriber", px=19, weight=QFont.Bold, color=TEXT))
        brand.addWidget(label("audio → text, in one click", family=MONO, px=12, color=MUTED))
        header.addLayout(brand)
        header.addStretch(1)
        header.addWidget(label(f"v{app_version()}", family=MONO, px=11, color=MUTED),
                         0, Qt.AlignTop)
        outer.addLayout(header)

        self.heading = label("Let's get you set up.", px=24, weight=QFont.Bold,
                             color=TEXT, wrap=True)
        self.heading.setContentsMargins(28, 16, 28, 0)
        outer.addWidget(self.heading)
        self.subtitle = label(
            "You'll need your own free Groq API key — it only takes about a minute.",
            px=14, color=TEXT_3, wrap=True)
        self.subtitle.setContentsMargins(28, 5, 28, 4)
        outer.addWidget(self.subtitle)

        # Scrollable steps, each followed by its screenshot.
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(28, 10, 28, 14)
        body.setSpacing(14)

        open_btn = QPushButton("Open Groq Console    ↗")
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(CONSOLE_URL))
        )
        body.addWidget(open_btn)

        self._add_step(body, 1, "Open the Groq Console and sign in.",
                       "step-1-signin.png")
        self._add_step(body, 2, "Go to API Keys, then Create API Key.",
                       "step-2-api-keys.png")
        self._add_step(body, 3, "Give it any name and hit Submit.",
                       "step-3-create-key.png")
        self._add_step(body, 4, "Copy the key — it starts with gsk_ and "
                                "shows only once.", "step-4-copy-key.png")
        body.addStretch(1)
        self._scroll.setWidget(content)
        outer.addWidget(self._scroll, 1)

        # Fixed footer: key box + save + privacy note.
        footer = QVBoxLayout()
        footer.setContentsMargins(28, 12, 28, 22)
        footer.setSpacing(10)

        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("gsk_••••••••••••••••••••••")
        self.key_input.returnPressed.connect(self._save)
        footer.addWidget(self.key_input)

        self.error_label = label("", px=13, color="#ff8a80", wrap=True)
        self.error_label.hide()
        footer.addWidget(self.error_label)

        self.save_btn = QPushButton("Save && Continue")
        self.save_btn.setObjectName("primary")
        self.save_btn.setMinimumHeight(48)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self._save)
        footer.addWidget(self.save_btn)

        note = QHBoxLayout()
        note.setSpacing(7)
        note.addWidget(_accent_dot(5))
        note.addWidget(label("Your key is stored only on this device — never uploaded.",
                             family=MONO, px=11, color=MUTED))
        note.addStretch(1)
        footer.addLayout(note)

        outer.addLayout(footer)

    def _add_step(self, layout, n, text, image):
        row = QHBoxLayout()
        row.setSpacing(13)
        row.addWidget(_circle_number(n), 0, Qt.AlignTop)
        row.addWidget(label(text, px=14, color=TEXT_2, wrap=True), 1)
        layout.addLayout(row)

        pix = QPixmap(resource_path(os.path.join("assets", image)))
        if not pix.isNull():
            holder = QLabel()
            holder.setStyleSheet(
                f"background: transparent; border: 1px solid {BORDER};"
            )
            holder.setPixmap(pix.scaledToWidth(560, Qt.SmoothTransformation))
            layout.addWidget(holder)
            self._step_images.append((holder, pix))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale_step_images()

    def _rescale_step_images(self):
        if not getattr(self, "_step_images", None):
            return
        avail = self._scroll.viewport().width() - 56  # content left+right margins
        if avail <= 0:
            return
        for holder, pix in self._step_images:
            width = min(avail, pix.width())
            holder.setPixmap(pix.scaledToWidth(width, Qt.SmoothTransformation))

    def set_reason(self, status):
        if status == "invalid":
            self.heading.setText("That key didn't work.")
            self.subtitle.setText(
                "It looks invalid or expired — let's add a new one.")
        elif status == "reenter":
            self.heading.setText("Enter a new API key.")
            self.subtitle.setText("Paste a fresh Groq key below.")
        else:
            self.heading.setText("Let's get you set up.")
            self.subtitle.setText(
                "You'll need your own free Groq API key — it only takes about a minute.")

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
                "Double-check it and try again.")
        elif status == "network_error":
            self._show_error(
                "Couldn't reach Groq to verify the key. "
                "Check your internet connection and try again.")
        else:
            self._show_error("Please paste your key first.")

    def _show_error(self, msg):
        self.error_label.setText(msg)
        self.error_label.show()


class DropZone(QFrame):
    """Dashed drop target — click to browse, or drop an audio file onto it."""

    clicked = Signal()
    fileDropped = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("dropzone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(15)

        self.icon = QLabel("↓")
        self.icon.setFixedSize(84, 84)
        self.icon.setAlignment(Qt.AlignCenter)
        self.icon.setFont(font(SANS, 34, QFont.Bold))
        self.icon.setStyleSheet(
            f"background: {TINT_DROP}; color: {ACCENT};"
            f" border: 1px solid {TINT_BORDER}; border-radius: 42px;")
        lay.addWidget(self.icon, 0, Qt.AlignHCenter)

        self.title = label("Drop your audio file here", px=18,
                           weight=QFont.DemiBold, color=TEXT)
        self.title.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.title)

        self.browse = label("or browse files", px=14, weight=QFont.Medium,
                            color=ACCENT)
        self.browse.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.browse)

        self.formats = label("MP3 · WAV · M4A · OGG · FLAC · MP4    —    max 25 MB",
                            family=MONO, px=11, color=MUTED)
        self.formats.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.formats)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(
                "#dropzone { background: #141a16; "
                f"border: 2px dashed {ACCENT}; border-radius: 16px; }}")

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")

    def dropEvent(self, event):
        self.setStyleSheet("")
        urls = event.mimeData().urls()
        if urls:
            self.fileDropped.emit(urls[0].toLocalFile())

    def show_file(self, name, sub):
        self.icon.setText("♪")
        self.title.setText(name)
        self.browse.setText(f"{sub}   ·   click to choose a different file")

    def show_empty(self):
        self.icon.setText("↓")
        self.title.setText("Drop your audio file here")
        self.browse.setText("or browse files")


class MainWidget(QWidget):
    """Main flow: pick a file, transcribe, then copy/save the result."""

    reenter_key = Signal(str)

    def __init__(self):
        super().__init__()
        self._file_path = None
        self._file_sub = ""
        self._language = None
        self._lang_label = ""
        self._thread = None
        self._worker = None
        self._original_text = ""
        self._hinglish_text = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top = QHBoxLayout()
        top.setContentsMargins(26, 20, 26, 8)
        top.addWidget(label("New transcription", family=MONO, px=11,
                            color=MUTED, spacing=1.5, upper=True))
        top.addStretch(1)
        reenter = QPushButton("Re-enter key")
        reenter.setObjectName("link")
        reenter.setCursor(Qt.PointingHandCursor)
        reenter.clicked.connect(lambda: self.reenter_key.emit("reenter"))
        top.addWidget(reenter)
        root.addLayout(top)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)
        self._stack.addWidget(self._build_pick_page())
        self._stack.addWidget(self._build_busy_page())
        self._stack.addWidget(self._build_result_page())
        self._stack.setCurrentIndex(0)

    # --- pages -----------------------------------------------------------
    def _build_pick_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(26, 14, 26, 22)
        lay.setSpacing(16)

        self.dropzone = DropZone()
        self.dropzone.clicked.connect(self._choose_file)
        self.dropzone.fileDropped.connect(self._set_file)
        lay.addWidget(self.dropzone, 1)

        bar = QHBoxLayout()
        bar.setSpacing(12)
        self.lang_combo = QComboBox()
        self.lang_combo.setCursor(Qt.PointingHandCursor)
        for lbl in core.LANGUAGES:
            self.lang_combo.addItem("Language:  " + lbl, lbl)
        bar.addWidget(self.lang_combo)
        bar.addStretch(1)
        self.transcribe_btn = QPushButton("Transcribe")
        self.transcribe_btn.setObjectName("primary")
        self.transcribe_btn.setMinimumWidth(150)
        self.transcribe_btn.setEnabled(False)
        self.transcribe_btn.setCursor(Qt.PointingHandCursor)
        self.transcribe_btn.clicked.connect(self._start)
        bar.addWidget(self.transcribe_btn)
        lay.addLayout(bar)

        self.helper = label("Add an audio file to enable transcription",
                           family=MONO, px=11, color=DISABLED)
        self.helper.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.helper)
        return page

    def _build_busy_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(26, 20, 26, 22)
        lay.addStretch(1)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.setAlignment(Qt.AlignCenter)
        row.addWidget(_accent_dot(10))
        row.addWidget(label("Transcribing…", px=19, weight=QFont.DemiBold,
                            color=TEXT))
        lay.addLayout(row)

        sub = label("Sending to Groq · whisper-large-v3", family=MONO, px=12,
                    color=MUTED)
        sub.setAlignment(Qt.AlignCenter)
        sub.setContentsMargins(0, 10, 0, 0)
        lay.addWidget(sub)

        lay.addStretch(1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        lay.addWidget(self.progress)
        cap = label("Usually under 10 seconds", family=MONO, px=11,
                    color=DISABLED)
        cap.setAlignment(Qt.AlignCenter)
        cap.setContentsMargins(0, 11, 0, 0)
        lay.addWidget(cap)
        return page

    def _build_result_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(26, 14, 26, 22)
        lay.setSpacing(14)

        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(self._make_chip())
        top.addStretch(1)
        self.lang_badge = QLabel("")
        self.lang_badge.setFont(font(MONO, 12, QFont.Medium))
        self.lang_badge.setStyleSheet(
            f"background: {TINT_BADGE}; color: {ACCENT_HI};"
            f" border: 1px solid {TINT_BORDER}; border-radius: 8px; padding: 6px 11px;")
        top.addWidget(self.lang_badge, 0, Qt.AlignVCenter)
        self._lang_toggle = self._make_lang_toggle()
        self._lang_toggle.hide()
        top.addWidget(self._lang_toggle, 0, Qt.AlignVCenter)
        lay.addLayout(top)

        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)
        self.result.setPlaceholderText("Your transcription will appear here.")
        lay.addWidget(self.result, 1)

        meta = QHBoxLayout()
        self.meta_label = label("", family=MONO, px=12, color=MUTED)
        meta.addWidget(self.meta_label)
        meta.addStretch(1)
        lay.addLayout(meta)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.copy_btn = QPushButton("Copy text")
        self.copy_btn.setObjectName("primary")
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.clicked.connect(self._copy)
        self.savetxt_btn = QPushButton("Save as .txt")
        self.savetxt_btn.setCursor(Qt.PointingHandCursor)
        self.savetxt_btn.clicked.connect(self._save_txt)
        actions.addWidget(self.copy_btn)
        actions.addWidget(self.savetxt_btn)
        actions.addStretch(1)
        newfile = QPushButton("↻  New file")
        newfile.setObjectName("link")
        newfile.setCursor(Qt.PointingHandCursor)
        newfile.clicked.connect(self._new_file)
        actions.addWidget(newfile)
        lay.addLayout(actions)
        return page

    def _make_chip(self):
        chip = QFrame()
        chip.setObjectName("chip")
        chip.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        h = QHBoxLayout(chip)
        h.setContentsMargins(13, 8, 15, 8)
        h.setSpacing(11)
        h.addWidget(label("♪", px=15, color=ACCENT))
        box = QVBoxLayout()
        box.setSpacing(2)
        self._chip_name = label("", px=13, weight=QFont.Medium, color=TEXT)
        self._chip_sub = label("", family=MONO, px=11, color=MUTED)
        box.addWidget(self._chip_name)
        box.addWidget(self._chip_sub)
        h.addLayout(box)
        return chip

    def _make_lang_toggle(self):
        frame = QFrame()
        frame.setObjectName("seg")
        frame.setStyleSheet(
            f"#seg {{ border: 1px solid {TINT_BORDER}; border-radius: 9px;"
            " background: transparent; }")
        row = QHBoxLayout(frame)
        row.setContentsMargins(3, 3, 3, 3)
        row.setSpacing(3)
        self._hindi_btn = QPushButton("Hindi")
        self._hindi_btn.setCursor(Qt.PointingHandCursor)
        self._hindi_btn.clicked.connect(self._show_hindi)
        self._hinglish_btn = QPushButton("Hinglish")
        self._hinglish_btn.setCursor(Qt.PointingHandCursor)
        self._hinglish_btn.clicked.connect(self._show_hinglish)
        row.addWidget(self._hindi_btn)
        row.addWidget(self._hinglish_btn)
        return frame

    def _seg_style(self, active):
        if active:
            bg, color, weight = TINT_BADGE, ACCENT_HI, 600
        else:
            bg, color, weight = "transparent", MUTED, 500
        base = (f"background: {bg}; color: {color}; border: none;"
                f" border-radius: 7px; padding: 5px 14px;"
                f" font-weight: {weight}; min-height: 0;")
        return f"QPushButton {{ {base} }} QPushButton:hover {{ {base} }}"

    def _set_lang_view(self, active):
        self._hindi_btn.setStyleSheet(self._seg_style(active == "hindi"))
        self._hinglish_btn.setStyleSheet(self._seg_style(active == "hinglish"))

    def _show_text(self, text):
        self.result.setPlainText(text)
        self.meta_label.setText(
            f"{len(text.split())} words · {len(text)} characters")

    def _show_hindi(self):
        self._set_lang_view("hindi")
        self._show_text(self._original_text)

    def _show_hinglish(self):
        if self._hinglish_text is not None:
            self._set_lang_view("hinglish")
            self._show_text(self._hinglish_text)
            return
        self._hindi_btn.setEnabled(False)
        self._hinglish_btn.setEnabled(False)
        self._hinglish_btn.setText("Converting…")
        self._rthread = QThread()
        self._rworker = RomaniseWorker(self._original_text, settings.get_api_key())
        self._rworker.moveToThread(self._rthread)
        self._rthread.started.connect(self._rworker.run)
        self._rworker.finished.connect(self._on_romanised)
        self._rworker.error.connect(self._on_romanise_error)
        self._rworker.finished.connect(self._rthread.quit)
        self._rworker.error.connect(self._rthread.quit)
        self._rthread.finished.connect(self._rthread.deleteLater)
        self._rthread.start()

    def _on_romanised(self, text):
        self._hinglish_text = text
        self._hindi_btn.setEnabled(True)
        self._hinglish_btn.setEnabled(True)
        self._hinglish_btn.setText("Hinglish")
        self._set_lang_view("hinglish")
        self._show_text(text)

    def _on_romanise_error(self, msg):
        self._hindi_btn.setEnabled(True)
        self._hinglish_btn.setEnabled(True)
        self._hinglish_btn.setText("Hinglish")
        self._set_lang_view("hindi")
        QMessageBox.critical(self, "Couldn't convert to Hinglish", msg)

    # --- file selection --------------------------------------------------
    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose audio file", "", AUDIO_FILTER)
        if path:
            self._set_file(path)

    def _set_file(self, path):
        if not path or not os.path.isfile(path):
            return
        size = os.path.getsize(path)
        if size > core.MAX_BYTES:
            QMessageBox.warning(
                self, "File too large",
                f"That file is {size / (1024 * 1024):.1f} MB, but Groq's "
                "limit is 25 MB.\nPlease choose a smaller file, or trim/"
                "compress this one first.")
            return
        self._file_path = path
        name = os.path.basename(path)
        ext = os.path.splitext(name)[1].lstrip(".").lower() or "audio"
        self._file_sub = f"{size / (1024 * 1024):.1f} MB · {ext}"
        self.dropzone.show_file(name, self._file_sub)
        self.transcribe_btn.setEnabled(True)
        self.helper.setText("Ready — hit Transcribe")

    # --- transcription ---------------------------------------------------
    def _start(self):
        if not self._file_path:
            return
        api_key = settings.get_api_key()
        self._lang_label = self.lang_combo.currentData()
        self._language = core.LANGUAGES[self._lang_label]

        self._stack.setCurrentIndex(1)  # busy
        self._thread = QThread()
        self._worker = TranscribeWorker(self._file_path, api_key, self._language)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.auth_error.connect(self._on_auth_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._worker.auth_error.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_finished(self, text):
        self._original_text = text
        self._hinglish_text = None
        self._show_text(text)
        self.lang_badge.setText(self._lang_label)
        self._chip_name.setText(os.path.basename(self._file_path))
        self._chip_sub.setText(self._file_sub)
        if core.has_devanagari(text):
            self.lang_badge.hide()
            self._hinglish_btn.setText("Hinglish")
            self._set_lang_view("hindi")
            self._lang_toggle.show()
        else:
            self._lang_toggle.hide()
            self.lang_badge.show()
        self._stack.setCurrentIndex(2)  # result

    def _on_error(self, msg):
        self._stack.setCurrentIndex(0)
        QMessageBox.critical(self, "Transcription failed", msg)

    def _on_auth_error(self):
        self._stack.setCurrentIndex(0)
        QMessageBox.warning(
            self, "API key rejected",
            "Your API key was rejected. Please enter a new one.")
        self.reenter_key.emit("invalid")

    # --- result actions --------------------------------------------------
    def _copy(self):
        QGuiApplication.clipboard().setText(self.result.toPlainText())
        self.copy_btn.setText("Copied ✓")
        QTimer.singleShot(1400, lambda: self.copy_btn.setText("Copy text"))

    def _save_txt(self):
        default_name = "transcription.txt"
        if self._file_path:
            stem = os.path.splitext(os.path.basename(self._file_path))[0]
            default_name = f"{stem}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save transcription", default_name, "Text files (*.txt)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.result.toPlainText())
        self.savetxt_btn.setText("Saved ✓")
        QTimer.singleShot(1400, lambda: self.savetxt_btn.setText("Save as .txt"))

    def _new_file(self):
        self._file_path = None
        self._file_sub = ""
        self._hinglish_text = None
        self._lang_toggle.hide()
        self.lang_badge.show()
        self.dropzone.show_empty()
        self.transcribe_btn.setEnabled(False)
        self.helper.setText("Add an audio file to enable transcription")
        self.result.clear()
        self._stack.setCurrentIndex(0)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmuggyTranscriber")
        self.resize(620, 780)
        self.setMinimumSize(520, 600)

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
    theme.apply(app)

    icon_path = resource_path(os.path.join("assets", "app-icon.png"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    _resolve_startup_screen(window)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
