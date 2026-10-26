"""Exercise the shipped Qt runtime without starting Clicky's background services."""
import json
import sys


def run():
    from PyQt6.QtCore import QT_VERSION_STR, qVersion
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
    from drawing import example_scene
    from ui.drawing_board import SketchCanvas
    from audio.devices import open_input_stream
    from audio.tts.edge_tts_provider import EdgeTTSProvider
    from importlib.metadata import version

    edge_version = version('edge-tts')
    assert tuple(map(int, edge_version.split('.')[:2])) >= (7, 3), 'Edge speech needs the updated handshake'

    app = QApplication.instance() or QApplication([])
    window = QWidget()
    layout = QVBoxLayout(window)
    layout.addWidget(QLabel("Clicky packaged startup check"))
    layout.addWidget(SketchCanvas(example_scene()))
    window.resize(800, 600)
    window.show()
    app.processEvents()
    image = QImage(window.size(), QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    window.render(painter)
    painter.end()
    assert not image.isNull()
    window.close()
    app.processEvents()
    report = {"ok": True, "qt_binding": QT_VERSION_STR, "qt_runtime": qVersion(),
              "checks": ["QtWidgets import", "native window", "Sketch rendering", "audio capture import", "Edge voice import"],
              "edge_tts": edge_version,
              "services_started": False}
    if "--smoke-report" in sys.argv:
        from pathlib import Path
        Path(sys.argv[sys.argv.index("--smoke-report") + 1]).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0
