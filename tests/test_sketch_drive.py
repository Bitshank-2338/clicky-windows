import asyncio
import json
from types import SimpleNamespace

import pytest

from drawing import validate_scene, example_scene, expression, wireframe
from drive import validate_plan, DriveController
from response_blocks import ResponseBlocks
from audio.narration import SentenceBuffer


@pytest.mark.parametrize("source", ["__import__('os').system('x')", "x.__class__", "[x for x in range(100)]", "2**1000", "open('secret')"])
def test_graph_does_not_execute_model_code(source):
    with pytest.raises((ValueError, SyntaxError)):
        expression(source, 1)


def test_math_and_mesh():
    assert expression("sin(pi/2) + x**2", 2) == pytest.approx(5)
    points, edges = wireframe("cube", .5, .3)
    assert len(points) == 8 and len(edges) == 12
    assert all(0 <= a < 8 and 0 <= b < 8 for a, b in edges)
    assert validate_scene(example_scene())["version"] == 1


@pytest.mark.parametrize("bad", [
    {"kind": "shell", "command": "anything"},
    {"kind": "click", "x": -1, "y": 50},
    {"kind": "click", "x": float('nan'), "y": 50},
    {"kind": "press", "keys": ["win", "l"]},
    {"kind": "type", "text": "hello\n"},
    {"kind": "wait", "seconds": 100},
    {"kind": "drag", "x": 10, "y": 10},
])
def test_drive_validates_entire_plan_before_input(bad):
    with pytest.raises(ValueError):
        validate_plan({"title": "Task", "actions": [{"kind": "click", "x": 5, "y": 5}, bad]})


def test_split_structured_response_never_speaks_json():
    source = 'Here is a cube.\n```clicky-scene\n' + json.dumps(example_scene()) + '\n```\nTry dragging it.'
    parser, visible, blocks = ResponseBlocks(), [], []
    for character in source:
        text, found = parser.feed(character)
        visible.append(text)
        blocks.extend(found)
    visible.append(parser.finish())
    assert "".join(visible) == "Here is a cube.\n\nTry dragging it."
    assert len(blocks) == 1 and blocks[0][0] == "scene"


def test_incomplete_drive_is_refused():
    parser = ResponseBlocks()
    parser.feed('```clicky-drive\n{"title":"unfinished"')
    with pytest.raises(ValueError):
        parser.finish()


def test_sentence_buffer_preserves_tags():
    buffer = SentenceBuffer()
    assert buffer.feed("Look here. [CIRCLE:20,30,40] ") == []
    assert buffer.feed("Next explanation.") == ["Look here. [CIRCLE:20,30,40]"]
    assert buffer.finish() == ["Next explanation."]


def test_native_canvas_renders_and_rotates(qt_app, tmp_path):
    from ui.drawing_board import DrawingBoard
    board = DrawingBoard(example_scene())
    board.show()
    qt_app.processEvents()
    image = board.canvas.grab()
    assert image.width() >= 480 and not image.isNull()
    assert image.save(str(tmp_path / "sketch.png"))
    before = board.canvas.yaw
    board._rotate()
    assert board.canvas.yaw > before
    board.close()


def test_drive_cancel_releases_held_mouse(monkeypatch):
    import tutor
    monkeypatch.setattr(tutor, "active_window_title", lambda: "Notepad")
    drive = DriveController()
    class Mouse:
        def __init__(self):
            self._position = (0, 0)
            self.held, self.released = [], []
        @property
        def position(self):
            return self._position
        @position.setter
        def position(self, value):
            self._position = value
            if self.held:
                drive.stop()
        def press(self, button):
            self.held.append(button)
        def release(self, button):
            self.released.append(button)
            self.held.remove(button)
    mouse = Mouse()
    plan = validate_plan({"title":"drag", "actions":[{"kind":"drag","x":0,"y":0,"to_x":500,"to_y":500}]})
    shot = SimpleNamespace(physical_left=0, physical_top=0, physical_width=1000, physical_height=1000)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(drive.run(plan, shot, mouse=mouse, keyboard=object()))
    assert not mouse.held and mouse.released
