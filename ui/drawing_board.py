"""A native Qt teaching canvas for Clicky's own Sketch format."""
import json
import math
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog

from drawing import validate_scene, expression, wireframe
from storage import atomic_write, data_dir

COLORS = {"blue": "#5597ff", "red": "#ff727c", "green": "#77dba3", "cyan": "#6ddbdc", "purple": "#bf9dff", "orange": "#ffb36d", "yellow": "#ffe18a", "white": "#eef2fb"}


class SketchCanvas(QWidget):
    question = pyqtSignal(str)

    def __init__(self, scene, parent=None):
        super().__init__(parent)
        self.scene = validate_scene(scene)
        self.yaw, self.pitch = 0.5, 0.3
        self._drag = None
        self._buttons = []
        self._button_widgets = []
        self.setMinimumSize(480, 360)
        self.setAccessibleName("Clicky interactive teaching canvas")
        self.rebuild_buttons()

    def rebuild_buttons(self):
        for button,item in self._button_widgets:button.deleteLater()
        self._button_widgets=[]
        for item in self.scene['objects']:
            if item['kind']!='button':continue
            button=QPushButton(item.get('text','Ask Clicky'),self)
            button.setAccessibleName(item.get('text','Ask Clicky'))
            button.setToolTip(item['question'])
            button.setStyleSheet('QPushButton { background:#203a5f; color:#eef2fb; border:2px solid #5597ff; border-radius:10px; padding:6px; } QPushButton:focus { border:3px solid #ffffff; }')
            button.clicked.connect(lambda _checked=False,question=item['question']:self.question.emit(question))
            self._button_widgets.append((button,item))
            button.show()
        self.position_buttons()

    def position_buttons(self):
        for button,item in self._button_widgets:
            button.setGeometry(round(item.get('x',50)/1000*self.width()),round(item.get('y',50)/1000*self.height()),round(item.get('w',350)/1000*self.width()),round(item.get('h',240)/1000*self.height()))

    def resizeEvent(self,event):
        self.position_buttons()
        super().resizeEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#101722"))
        p.scale(self.width() / 1000, self.height() / 1000)
        self._buttons = []
        for item in self.scene["objects"]:
            color = QColor(COLORS.get(item.get("color", "blue"), COLORS["blue"]))
            p.setPen(QPen(color, 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            x, y = item.get("x", 50), item.get("y", 50)
            w, h = item.get("w", 350), item.get("h", 240)
            kind = item["kind"]
            if kind in {"text", "button"}:
                rect = QRectF(x, y, w, h if kind == "button" else 110)
                if kind == "button":
                    p.setBrush(QColor("#203a5f"))
                    p.drawRoundedRect(rect, 15, 15)
                    self._buttons.append((rect, item["question"]))
                p.setPen(QColor("#eef2fb"))
                p.setFont(QFont("Segoe UI", 22))
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter if kind == "button" else Qt.TextFlag.TextWordWrap, item.get("text", ""))
            elif kind in {"line", "arrow"}:
                x2, y2 = item.get("x2", x + 100), item.get("y2", y)
                p.drawLine(QPointF(x, y), QPointF(x2, y2))
                if kind == "arrow":
                    angle = math.atan2(y2 - y, x2 - x)
                    for side in (-0.5, 0.5):
                        p.drawLine(QPointF(x2, y2), QPointF(x2 - 20 * math.cos(angle + side), y2 - 20 * math.sin(angle + side)))
            elif kind == "rect":
                p.drawRoundedRect(QRectF(x, y, w, h), 10, 10)
            elif kind == "circle":
                r = item.get("r", 60)
                p.drawEllipse(QPointF(x, y), r, r)
            elif kind in {"cube", "sphere"}:
                points, edges = wireframe(kind, self.yaw, self.pitch)
                r = item.get("r", 100)
                for a, b in edges:
                    p.drawLine(QPointF(x + points[a][0] * r, y + points[a][1] * r), QPointF(x + points[b][0] * r, y + points[b][1] * r))
            elif kind == "chart":
                values = item["values"]
                minimum, maximum = min(0, min(values)), max(0, max(values))
                span = maximum - minimum or 1
                baseline = y + h * maximum / span
                p.drawLine(QPointF(x, baseline), QPointF(x + w, baseline))
                for i, value in enumerate(values):
                    bar = w / len(values)
                    top = baseline - value / span * h
                    p.fillRect(QRectF(x + i * bar + 3, min(baseline, top), max(1, bar - 6), abs(top - baseline)), color)
                    labels = item.get("labels", [])
                    if i < len(labels):
                        p.setFont(QFont("Segoe UI", 14))
                        p.drawText(QRectF(x + i * bar, y + h + 8, bar, 50), Qt.AlignmentFlag.AlignCenter, labels[i])
            elif kind == "graph":
                lo, hi = item.get("min", -5), item.get("max", 5)
                samples = []
                for i in range(161):
                    argument = lo + (hi - lo) * i / 160
                    try:
                        value = expression(item["expression"], argument)
                        samples.append(value if math.isfinite(value) and abs(value) < 1e6 else None)
                    except (ValueError, ZeroDivisionError, OverflowError):
                        samples.append(None)
                valid = [n for n in samples if n is not None]
                if valid:
                    low, high = min(0, min(valid)), max(0, max(valid))
                    span = high - low or 1
                    p.setPen(QPen(QColor("#38485e"), 2))
                    axis_y = y + h - (0 - low) / span * h
                    p.drawLine(QPointF(x, axis_y), QPointF(x + w, axis_y))
                    path, connected = QPainterPath(), False
                    for i, value in enumerate(samples):
                        if value is None:
                            connected = False
                            continue
                        point = QPointF(x + i / 160 * w, y + h - (value - low) / span * h)
                        path.lineTo(point) if connected else path.moveTo(point)
                        connected = True
                    p.setPen(QPen(color, 4))
                    p.drawPath(path)
        p.end()

    def mousePressEvent(self, event):
        point = QPointF(event.position().x() / self.width() * 1000, event.position().y() / self.height() * 1000)
        for rect, question in self._buttons:
            if rect.contains(point):
                self.question.emit(question)
                return
        self._drag = event.position()

    def mouseMoveEvent(self, event):
        if self._drag is not None:
            delta = event.position() - self._drag
            self.yaw += delta.x() / 120
            self.pitch += delta.y() / 120
            self._drag = event.position()
            self.update()

    def mouseReleaseEvent(self, _event):
        self._drag = None


class DrawingBoard(QWidget):
    question = pyqtSignal(str)
    narrate = pyqtSignal(str)

    def __init__(self, scene, parent=None):
        super().__init__(parent)
        self.canvas = SketchCanvas(scene)
        self._narration = [self.canvas.scene.get('narration','')]
        self.setWindowTitle(self.canvas.scene["title"] or "Clicky Sketch")
        self.resize(850, 640)
        layout = QVBoxLayout(self)
        tools = QHBoxLayout()
        for text, callback in (("Save lesson", self.save), ("Open lesson", self.open), ("Replay voice", self.replay), ("Export PNG", self.export), ("Rotate / pause", self.toggle_rotation)):
            button = QPushButton(text)
            button.clicked.connect(callback)
            tools.addWidget(button)
        layout.addLayout(tools)
        layout.addWidget(self.canvas, stretch=1)
        self.caption = QLabel()
        self.caption.setWordWrap(True)
        self.caption.setAccessibleName("Lesson narration caption")
        layout.addWidget(self.caption)
        self.canvas.question.connect(self.question)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._rotate)

    def _rotate(self):
        self.canvas.yaw += 0.015
        self.canvas.update()

    def toggle_rotation(self):
        self._timer.stop() if self._timer.isActive() else self._timer.start()

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)

    def save(self):
        folder = data_dir() / "lessons"
        folder.mkdir(exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, "Save Clicky lesson", str(folder / "lesson.clicky.json"), "Clicky lesson (*.clicky.json)")
        if path:
            self.canvas.scene['narration']='\n'.join(self._narration).strip()[-20000:]
            atomic_write(Path(path), json.dumps(self.canvas.scene, ensure_ascii=False, indent=2).encode("utf-8"))

    def set_caption(self,text):
        self.caption.setText(text)
        if text and (not self._narration or self._narration[-1]!=text):self._narration.append(text)

    def replay(self):
        text='\n'.join(self._narration).strip()
        if text:self.narrate.emit(text)

    def open(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Clicky lesson", str(data_dir() / "lessons"), "Clicky lesson (*.json)")
        if path:
            from PyQt6.QtWidgets import QMessageBox
            try:
                if Path(path).stat().st_size > 200000:
                    raise ValueError("Lesson file is too large")
                self.canvas.scene = validate_scene(json.loads(Path(path).read_text(encoding="utf-8")))
                self.canvas.rebuild_buttons()
                self._narration=[self.canvas.scene.get('narration','')]
                self.canvas.update()
                self.setWindowTitle(self.canvas.scene["title"])
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Could not open lesson", str(exc))

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export lesson image", "lesson.png", "PNG (*.png)")
        if path:
            if not self.canvas.grab().save(path):
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Export failed", "Could not write that image")
