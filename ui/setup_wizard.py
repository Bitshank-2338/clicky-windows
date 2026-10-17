"""
First-run setup wizard.

Shown once on the first launch (or whenever the user clicks
"Tray → Run setup again…"). Walks the user through:

  0. What Clicky is and how to use it
  1. Pick an engine — free local Ollama, or a cloud API key
  2. Detect Ollama       → start it if installed, install only if truly absent
  3. Detect text model   → pull if missing
  4. Detect vision model → pull if missing  (optional, larger)

Everything is optional — the user can Skip at any step. The wizard never
blocks the main app from starting.

Two things this deliberately gets right, because the shipped 1.2.0 build got
them wrong:

  • Ollama detection looks for the *binary*, not just a live server, and
    starts an installed-but-stopped copy instead of re-downloading 700 MB.
  • There is a real API-key screen, so "Skip — I'll use an API key" leads
    somewhere instead of dead-ending at a file the user has to go find.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
)

from ai import ollama_bootstrap as ob
from config import cfg


# Marker file: the wizard skips itself if this exists.
def _flag_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = Path(base) / "Clicky"
    d.mkdir(parents=True, exist_ok=True)
    return d / "setup_complete.flag"


def setup_already_ran() -> bool:
    return _flag_path().exists()


def mark_setup_complete() -> None:
    try:
        _flag_path().write_text("ok")
    except Exception:
        pass


def _shared_model() -> bool:
    """True when one model serves both text and screen questions (the default)."""
    return cfg.ollama_text_model == cfg.ollama_vision_model


def _size_hint(name: str) -> str:
    """Download size for a model tag, from the curated registry."""
    from ai.ollama_models_registry import RECOMMENDED_TEXT, RECOMMENDED_VISION
    for rec in (*RECOMMENDED_VISION, *RECOMMENDED_TEXT):
        if rec.name == name:
            return rec.size
    return "a few GB"


def _pretty_hotkey() -> str:
    return "+".join(p.strip().capitalize() for p in cfg.hotkey.split("+"))


# ─── Wizard ───────────────────────────────────────────────────────────────────

class SetupWizard(QDialog):
    """One-window wizard: welcome → engine choice → Ollama/keys → done."""

    progress_signal = pyqtSignal(str, float)
    finished_signal = pyqtSignal(bool, str)   # ok, message

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("კლიკის დაყენება")
        self.setModal(False)
        self.setMinimumSize(600, 420)
        self.setStyleSheet("""
            QDialog { background: #0e1014; color: #e8eaed; }
            QLabel  { color: #e8eaed; }
            QLabel#title { font-size: 22px; font-weight: 700; }
            QLabel#subtitle { color: #a0a3a8; font-size: 13px; }
            QLabel#status { color: #c8cbd0; font-size: 13px; }
            QPushButton {
                background: #1f6feb; color: white; border: none;
                padding: 10px 18px; border-radius: 8px;
                font-weight: 600; font-size: 13px;
            }
            QPushButton:hover  { background: #2f7fff; }
            QPushButton:disabled { background: #333; color: #888; }
            QPushButton#secondary {
                background: transparent; color: #a0a3a8;
                border: 1px solid #2a2d33;
            }
            QPushButton#secondary:hover { color: #e8eaed; border-color: #444; }
            QProgressBar {
                background: #1a1d22; border: 1px solid #2a2d33;
                border-radius: 6px; height: 12px; text-align: center;
                color: #e8eaed; font-size: 11px;
            }
            QProgressBar::chunk { background: #1f6feb; border-radius: 6px; }
        """)

        self._keys_dialog = None
        self._worker: threading.Thread | None = None
        self._next_step = "done"

        self._build_ui()
        self.progress_signal.connect(self._on_progress)
        self.finished_signal.connect(self._on_finished)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(14)

        self.title = QLabel("მოგესალმებათ კლიკი")
        self.title.setObjectName("title")
        layout.addWidget(self.title)

        self.subtitle = QLabel("")
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)

        self.status = QLabel("")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        layout.addSpacing(8)
        layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        layout.addWidget(self.progress)

        layout.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.skip_btn = QPushButton("გამოტოვება")
        self.skip_btn.setObjectName("secondary")
        self.skip_btn.clicked.connect(self._on_skip)
        btn_row.addWidget(self.skip_btn)

        btn_row.addStretch(1)

        # Middle button — the "other option" on branching pages.
        self.alt_btn = QPushButton("")
        self.alt_btn.setObjectName("secondary")
        self.alt_btn.clicked.connect(self._on_alt)
        self.alt_btn.hide()
        btn_row.addWidget(self.alt_btn)

        self.action_btn = QPushButton("დაწყება")
        self.action_btn.clicked.connect(self._on_action)
        btn_row.addWidget(self.action_btn)

        layout.addLayout(btn_row)

        self._set_step("welcome")

    # ── State machine ────────────────────────────────────────────────────────

    def _set_step(self, step: str):
        self._step = step
        self.progress.hide()
        self.progress.setValue(0)
        self.status.setText("")
        self.alt_btn.hide()
        self.action_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        self.skip_btn.show()
        self.skip_btn.setText("გამოტოვება")

        if step == "welcome":
            self.title.setText("გაიცანით კლიკი")
            self.subtitle.setText(
                "კლიკი არის AI მასწავლებელი, რომელიც კურსორთან ცხოვრობს და "
                "თქვენს ეკრანს ხედავს — ამიტომ საჭირო ადგილს პირდაპირ გაჩვენებთ.\n\n"
                f"•  დააჭირეთ {_pretty_hotkey()} ან უბრალოდ თქვით „კლიკი“, "
                "შემდეგ ხმამაღლა დასვით კითხვა.\n"
                "•  კლიკი ხმით გიპასუხებთ და ეკრანზე ისრებს, წრეებს და "
                "წარწერებს დახატავს.\n"
                "•  ჰკითხეთ ყველაფერი, რასაც ეკრანზე ხედავთ — დოკუმენტი, "
                "შეცდომის შეტყობინება, პარამეტრების გვერდი.\n"
                "•  ყველა პარამეტრი ხატულაშია, საათის გვერდით.\n\n"
                "ახლა აირჩიეთ AI ძრავა. ეს დაახლოებით ერთ წუთს წაიღებს."
            )
            self.action_btn.setText("გაგრძელება")
            self.skip_btn.setText("დაყენების გამოტოვება")

        elif step == "engine":
            self.title.setText("აირჩიეთ AI ძრავა")
            self.subtitle.setText(
                "უფასო და ინტერნეტის გარეშე — Ollama AI-ს თქვენს კომპიუტერზე უშვებს. "
                "არც ანგარიში, არც API გასაღები, არაფერი გადის კომპიუტერიდან. "
                "საჭიროა მოდელის ერთჯერადი ჩამოტვირთვა (რამდენიმე GB).\n\n"
                "ან გამოიყენეთ საკუთარი გასაღები — Claude, OpenAI ან Gemini. უფრო "
                "სწრაფი და ჭკვიანი, მაგრამ ფასიანია და ეკრანის სურათი მათ "
                "სერვერებზე იგზავნება.\n\n"
                "ამის შეცვლა ნებისმიერ დროს შეგიძლიათ ხატულის მენიუდან."
            )
            self.action_btn.setText("Ollama — უფასოდ")
            self.alt_btn.setText("API გასაღებს გამოვიყენებ")
            self.alt_btn.show()

        elif step == "detect":
            self.title.setText("Ollama-ს ვამოწმებ…")
            self.subtitle.setText(
                "ჩამოტვირთვამდე ვამოწმებ, უკვე დაყენებულია თუ არა Ollama."
            )
            self.action_btn.setEnabled(False)
            self.skip_btn.setEnabled(False)
            self.status.setText("მოწმდება…")

        elif step == "install":
            self.title.setText("Ollama-ს დაყენება")
            self.subtitle.setText(
                "ამ კომპიუტერზე Ollama ჯერ არ არის. ეს არის ძრავა, რომელიც AI-ს "
                "ადგილზე უშვებს — ჩვენ ჩამოვტვირთავთ და დავაყენებთ (≈700 MB)."
            )
            self.action_btn.setText("Ollama-ს დაყენება")

        elif step == "installing":
            self.title.setText("Ollama ყენდება…")
            self.subtitle.setText(
                "ოფიციალური ინსტალერი ჩამოიტვირთება ollama.com-დან და გაეშვება. "
                "დაეთანხმეთ ყველა გამოჩენილ ფანჯარას (UAC / ინსტალერი)."
            )
            self.action_btn.setEnabled(False)
            self.skip_btn.setEnabled(False)
            self.status.setText("ჩამოტვირთვა იწყება…")
            self.progress.show()

        elif step == "text_model":
            name = cfg.ollama_text_model
            if _shared_model():
                # One multimodal model covers both jobs, so there is only one
                # download to offer — not a text step followed by a vision step
                # that asks for the same file again.
                self.title.setText("კლიკის AI მოდელის ჩამოტვირთვა")
                self.subtitle.setText(
                    f"ჩამოიტვირთება {name} (≈{_size_hint(name)}). ის პასუხობს კითხვებს და "
                    f"კითხულობს ეკრანს — მითითება, სურათები, დიაგრამები — ასე რომ, "
                    f"მეტი მოდელი არ დაგჭირდებათ."
                )
                self.skip_btn.setText("გამოტოვება — მოგვიანებით დავამატებ")
            else:
                self.title.setText("ტექსტური მოდელის ჩამოტვირთვა")
                self.subtitle.setText(
                    f"ჩამოიტვირთება {name} (≈{_size_hint(name)}). სწორედ ის პასუხობს, "
                    f"როცა კლიკის კითხვას უსვამთ."
                )
                self.skip_btn.setText("ამ მოდელის გამოტოვება")
            self.action_btn.setText(f"{name}-ის ჩამოტვირთვა")

        elif step == "pulling_text":
            self.title.setText(f"იტვირთება {cfg.ollama_text_model}…")
            self.action_btn.setEnabled(False)
            self.skip_btn.setEnabled(False)
            self.status.setText("Ollama-სთან დაკავშირება…")
            self.progress.show()

        elif step == "vision_model":
            name = cfg.ollama_vision_model
            self.title.setText("ხედვის მოდელის ჩამოტვირთვა (არასავალდებულო)")
            self.subtitle.setText(
                f"ჩამოიტვირთება {name} (≈{_size_hint(name)}). საჭიროა მხოლოდ მაშინ, როცა კლიკი "
                f"ეკრანს კითხულობს — მითითება, სურათები, დიაგრამები. შეგიძლიათ "
                f"გამოტოვოთ და მოგვიანებით ხატულის მენიუდან დაამატოთ."
            )
            self.action_btn.setText(f"{name}-ის ჩამოტვირთვა")
            self.skip_btn.setText("გამოტოვება — მოგვიანებით")

        elif step == "pulling_vision":
            self.title.setText(f"იტვირთება {cfg.ollama_vision_model}…")
            self.action_btn.setEnabled(False)
            self.skip_btn.setEnabled(False)
            self.status.setText("Ollama-სთან დაკავშირება…")
            self.progress.show()

        elif step == "keys":
            self.title.setText("API გასაღების დამატება")
            self.subtitle.setText(
                "ჩასვით Claude-ის, OpenAI-ის ან Gemini-ის გასაღები. კლიკი შეინახავს და "
                "მაშინვე დაიწყებს გამოყენებას — მოგვიანებით შეცვლა შეგიძლიათ აქ: "
                "ხატულა → პარამეტრები და დიაგნოსტიკა → API გასაღებები."
            )
            self.action_btn.setText("API გასაღებების გახსნა…")
            self.alt_btn.setText("ამის ნაცვლად Ollama")
            self.alt_btn.show()
            self.skip_btn.setText("ახლა გამოტოვება")
            self._refresh_key_status()

        elif step == "done":
            self.title.setText("ყველაფერი მზადაა 🎉")
            providers = cfg.describe()
            self.subtitle.setText(
                f"კლიკი მზადაა და მუშაობს {providers['llm']}-ზე.\n\n"
                f"•  დააჭირეთ {_pretty_hotkey()} და ილაპარაკეთ, ან თქვით „კლიკი“.\n"
                "•  გრძელი პასუხის შესაწყვეტად დააჭირეთ Esc-ს.\n"
                "•  პარამეტრებისთვის ხატულაზე დააჭირეთ მარჯვენა ღილაკით.\n"
                "•  PDF ფაილი პანელზე გადმოიტანეთ და ჰკითხეთ მის შესახებ."
            )
            self.action_btn.setText("დავიწყოთ")
            self.skip_btn.hide()
            mark_setup_complete()

    def _refresh_key_status(self):
        have = [
            label for env_var, (_, label) in cfg.API_KEY_FIELDS.items()
            if cfg.get_api_key(env_var)
        ]
        self.status.setText(
            f"დაყენებულია: {', '.join(have)}" if have else "გასაღებები ჯერ არ არის."
        )

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_action(self):
        s = self._step

        if s == "welcome":
            self._set_step("engine")

        elif s == "engine":
            self._set_step("detect")
            self._start_detect_worker()

        elif s == "install":
            self._set_step("installing")
            self._start_install_worker()

        elif s == "text_model":
            self._set_step("pulling_text")
            self._start_pull_worker(cfg.ollama_text_model)

        elif s == "vision_model":
            self._set_step("pulling_vision")
            self._start_pull_worker(cfg.ollama_vision_model)

        elif s == "keys":
            self._open_keys_dialog()

        elif s == "done":
            self.accept()

    def _on_alt(self):
        if self._step == "engine":
            self._set_step("keys")
        elif self._step == "keys":
            self._set_step("detect")
            self._start_detect_worker()

    def _on_skip(self):
        s = self._step
        if s in ("welcome", "engine", "install", "keys"):
            mark_setup_complete()
            self.reject()
        elif s == "text_model":
            # Skipping a shared model means skipping the only download there is.
            self._set_step("done" if _shared_model() else "vision_model")
        elif s == "vision_model":
            self._set_step("done")

    def _open_keys_dialog(self):
        from ui.api_keys_dialog import ApiKeysDialog
        dlg = ApiKeysDialog(self)
        dlg.keys_saved.connect(self._refresh_key_status)
        dlg.finished.connect(lambda _: self._on_keys_closed())
        dlg.show()
        self._keys_dialog = dlg   # keep a ref so Qt doesn't GC it

    def _on_keys_closed(self):
        self._refresh_key_status()
        if any(cfg.get_api_key(v) for v in cfg.API_KEY_FIELDS):
            self._set_step("done")

    # ── Workers (run on a background thread) ─────────────────────────────────

    def _start_detect_worker(self):
        """Find/start Ollama without downloading. Never blocks the UI thread."""
        def _worker():
            try:
                if ob.is_ollama_running():
                    self.finished_signal.emit(True, "running")
                    return
                if ob.is_ollama_installed():
                    self.progress_signal.emit(
                        "Ollama დაყენებულია — ვრთავ…", 0.0
                    )
                    ok = ob.ensure_ollama_running(timeout=30)
                    self.finished_signal.emit(
                        ok,
                        "running" if ok else
                        "Ollama დაყენებულია, მაგრამ არ ჩაირთო. გახსენით Start "
                        "მენიუდან და დააჭირეთ „თავიდან ცდა“."
                    )
                    return
                self.finished_signal.emit(False, "missing")
            except Exception as e:
                self.finished_signal.emit(False, f"Ollama-ს შემოწმება ვერ მოხერხდა: {e}")

        self._worker = threading.Thread(target=_worker, daemon=True)
        self._worker.start()

    def _start_install_worker(self):
        def _worker():
            try:
                self.progress_signal.emit("Ollama-ს ინსტალერი იტვირთება…", 0.0)
                path = ob.download_ollama_installer(
                    on_progress=lambda pct: self.progress_signal.emit(
                        f"იტვირთება… {pct:.0f}%", pct
                    )
                )
                self.progress_signal.emit(
                    "ინსტალერი იხსნება (დაეთანხმეთ UAC ფანჯრებს)…", 100.0
                )
                ob.run_ollama_installer(path, silent=False)
                self.progress_signal.emit("ველოდები Ollama-ს ჩართვას…", 100.0)
                if ob.ensure_ollama_running(timeout=90):
                    self.finished_signal.emit(True, "")
                else:
                    self.finished_signal.emit(
                        False,
                        "Ollama დაყენდა, მაგრამ არ ჩაირთო. გადატვირთეთ კომპიუტერი "
                        "ან გახსენით Ollama Start მენიუდან და თავიდან გაუშვით დაყენება."
                    )
            except Exception as e:
                self.finished_signal.emit(False, f"დაყენება ვერ მოხერხდა: {e}")

        self._worker = threading.Thread(target=_worker, daemon=True)
        self._worker.start()

    def _start_pull_worker(self, model: str):
        def _worker():
            if ob.is_model_installed(model):
                self.finished_signal.emit(True, "")
                return
            ok = ob.pull_model(
                model,
                on_progress=lambda status, pct: self.progress_signal.emit(
                    f"{status} ({pct:.0f}%)" if pct else status, pct
                ),
            )
            self.finished_signal.emit(ok, "" if ok else f"{model} ვერ ჩამოიტვირთა.")

        self._worker = threading.Thread(target=_worker, daemon=True)
        self._worker.start()

    def _on_progress(self, status: str, pct: float):
        self.status.setText(status)
        self.progress.setValue(int(pct))

    def _on_finished(self, ok: bool, msg: str):
        s = self._step

        if s == "detect":
            if ok:
                self._goto_next_model_step()
            elif msg == "missing":
                self._set_step("install")
            else:
                self._set_step("install")
                self.status.setText(f"⚠️ {msg}")
            return

        if not ok:
            self.status.setText(f"⚠️ {msg}")
            self.action_btn.setEnabled(True)
            self.skip_btn.setEnabled(True)
            self.action_btn.setText("თავიდან ცდა")
            return

        if s == "installing":
            self._goto_next_model_step()
        elif s == "pulling_text":
            # Re-evaluates what is installed, so a shared text/vision model
            # skips the vision step instead of offering the same download twice.
            self._goto_next_model_step()
        elif s == "pulling_vision":
            self._set_step("done")

    def _goto_next_model_step(self):
        # Skip straight past anything that's already pulled.
        if not ob.is_model_installed(cfg.ollama_text_model):
            self._set_step("text_model")
        elif not ob.is_model_installed(cfg.ollama_vision_model):
            self._set_step("vision_model")
        else:
            self._set_step("done")


def maybe_show_setup_wizard(parent=None) -> SetupWizard | None:
    """Open the wizard on first run.

    Unlike 1.2.0 this shows even when Ollama is already healthy — a silent
    first launch left new users with no idea what Clicky was or how to talk to
    it. The Ollama steps still skip themselves when there's nothing to do.
    """
    if setup_already_ran():
        return None

    w = SetupWizard(parent)
    w.show()
    return w
