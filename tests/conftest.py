import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
_data = tempfile.TemporaryDirectory(prefix="clicky-tests-")
os.environ["CLICKY_DATA_DIR"] = _data.name
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setenv("CLICKY_DATA_DIR", str(tmp_path))


@pytest.fixture(scope="session")
def qt_app():
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QFontDatabase, QFont
    app = QApplication.instance() or QApplication([])
    if not QFontDatabase.families():
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
    app.setFont(QFont('Segoe UI',10))
    yield app
