"""Clicky Sketch: an original declarative lesson format; model output is never executed."""
import ast
import math
import operator

KINDS = {"text", "line", "arrow", "rect", "circle", "chart", "graph", "cube", "sphere", "button"}
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow}
_FUNCTIONS = {name: getattr(math, name) for name in ("sin", "cos", "tan", "sqrt", "log", "exp")}
_FUNCTIONS["abs"] = abs

SKETCH_PROMPT = '''
CLICKY SKETCH: for visual explanations emit one fenced clicky-scene JSON block after your narration.
Schema: {"version":1,"title":"Lesson","objects":[{"kind":"cube","x":500,"y":450,"r":160,"color":"cyan"}]}.
Coordinates/sizes are 0–1000. Objects: text (x,y,text); line/arrow (x,y,x2,y2); rect (x,y,w,h); circle/cube/sphere (x,y,r); chart (x,y,w,h,values,labels); graph (x,y,w,h,expression,min,max); button (x,y,w,h,text,question). Graphs support x, numbers, arithmetic, sin/cos/tan/sqrt/log/exp/abs. Buttons ask questions, never execute code. Colors: blue/red/green/orange/purple/white/cyan/yellow.
'''


def expression(source, x):
    tree = ast.parse(source, mode="eval")
    if len(list(ast.walk(tree))) > 64:
        raise ValueError("Graph expression is too complex")
    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float) and abs(node.value) <= 1000000:
            return node.value
        if isinstance(node, ast.Name) and node.id in {"x", "pi", "e"}:
            return {"x": x, "pi": math.pi, "e": math.e}[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return -visit(node.operand) if isinstance(node.op, ast.USub) else visit(node.operand)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            a, b = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and (abs(b) > 8 or abs(a) > 1000000):
                raise ValueError("Graph exponent exceeds the rendering limit")
            result = _OPS[type(node.op)](a, b)
            if not isinstance(result, (int, float)) or not math.isfinite(result) or abs(result) > 1e12:
                raise ValueError("Graph result exceeds the rendering limit")
            return result
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS and len(node.args) == 1 and not node.keywords:
            return _FUNCTIONS[node.func.id](visit(node.args[0]))
        raise ValueError("Use x, numbers, arithmetic, sin/cos/tan/sqrt/log/exp/abs only")
    return visit(tree)


def validate_scene(value):
    if not isinstance(value, dict) or set(value) - {"version", "title", "objects", "narration"} or value.get("version") != 1:
        raise ValueError("Sketch needs version 1, title, and objects")
    if not isinstance(value.get("title"), str) or len(value["title"]) > 160:
        raise ValueError("Sketch title is too long")
    objects = value.get("objects")
    if not isinstance(value.get('narration',''),str) or len(value.get('narration',''))>20000:
        raise ValueError('Saved narration is too long')
    if not isinstance(objects, list) or not 1 <= len(objects) <= 80:
        raise ValueError("Sketch needs 1–80 objects")
    fields = {"kind", "x", "y", "w", "h", "x2", "y2", "r", "text", "color", "values", "labels", "expression", "min", "max", "question"}
    for item in objects:
        if not isinstance(item, dict) or item.get("kind") not in KINDS or set(item) - fields:
            raise ValueError("Unknown Sketch object or field")
        for key in {"x", "y", "w", "h", "x2", "y2", "r"} & item.keys():
            number = item[key]
            if type(number) not in (int, float) or not math.isfinite(number) or not 0 <= number <= 1000:
                raise ValueError("Sketch positions/sizes must be 0–1000")
        for key in {"text", "question", "color", "expression"} & item.keys():
            if not isinstance(item[key], str) or len(item[key]) > (120 if key == "expression" else 2000):
                raise ValueError("Sketch text exceeds its limit")
        if "color" in item and item["color"] not in {"blue", "red", "green", "orange", "purple", "white", "cyan", "yellow"}:
            raise ValueError("Unsupported Sketch color")
        if item["kind"] == "chart":
            values = item.get("values")
            if not isinstance(values, list) or not 1 <= len(values) <= 40 or any(type(n) not in (int, float) or not math.isfinite(n) or abs(n) > 1e9 for n in values):
                raise ValueError("Charts need 1–40 finite values")
            labels = item.get("labels", [])
            if not isinstance(labels, list) or len(labels) > 40 or any(not isinstance(label, str) or len(label) > 40 for label in labels):
                raise ValueError("Chart labels are too long")
        if item["kind"] == "graph":
            if not isinstance(item.get("expression"), str):
                raise ValueError("Graph needs an expression")
            lo, hi = item.get("min", -5), item.get("max", 5)
            if any(type(n) not in (int, float) or not math.isfinite(n) or abs(n) > 1000 for n in (lo, hi)) or lo >= hi:
                raise ValueError("Invalid graph range")
            try:
                expression(item["expression"], (lo + hi) / 2)
            except (ZeroDivisionError, OverflowError):
                pass
        if item["kind"] == "button" and not item.get("question", "").strip():
            raise ValueError("Lesson buttons need a follow-up question")
    return {"version": 1, "title": value["title"], "objects": [dict(item) for item in objects], 'narration':value.get('narration','')}


def wireframe(kind, yaw, pitch):
    if kind == "cube":
        vertices = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
        edges = [(a, b) for a in range(8) for b in range(a + 1, 8) if sum(vertices[a][k] != vertices[b][k] for k in range(3)) == 1]
    else:
        vertices, edges = [], []
        for axis in range(3):
            start = len(vertices)
            for i in range(48):
                a = i * 2 * math.pi / 48
                point = [math.cos(a), math.sin(a), 0]
                vertices.append(tuple(point[(k + axis) % 3] for k in range(3)))
                edges.append((start + i, start + (i + 1) % 48))
    points = []
    for x, y, z in vertices:
        x, z = x * math.cos(yaw) + z * math.sin(yaw), -x * math.sin(yaw) + z * math.cos(yaw)
        y, z = y * math.cos(pitch) - z * math.sin(pitch), y * math.sin(pitch) + z * math.cos(pitch)
        depth = 4 / (4 + z)
        points.append((x * depth, y * depth))
    return points, edges


def example_scene():
    return {"version": 1, "title": "Clicky Sketch — explore and ask", "objects": [
        {"kind": "text", "x": 45, "y": 80, "text": "A graph and a shape you can turn"},
        {"kind": "graph", "x": 60, "y": 200, "w": 420, "h": 480, "expression": "sin(x)", "min": -6.28, "max": 6.28},
        {"kind": "cube", "x": 730, "y": 420, "r": 150, "color": "cyan"},
        {"kind": "button", "x": 70, "y": 810, "w": 420, "h": 85, "text": "Explain the sine curve", "question": "Explain the sine curve in the lesson board"},
        {"kind": "text", "x": 570, "y": 760, "text": "Drag to rotate the 3D shape"},
    ]}
