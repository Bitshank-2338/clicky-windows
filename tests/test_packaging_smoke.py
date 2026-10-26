import os
import subprocess
import sys
from pathlib import Path


def test_smoke_startup_without_services(tmp_path):
    report = tmp_path / "startup.json"
    env = dict(os.environ, CLICKY_DATA_DIR=str(tmp_path / "user-data"))
    result = subprocess.run([sys.executable, "main.py", "--smoke-test", "--smoke-report", str(report)],
                            cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    import json
    assert json.loads(report.read_text())["ok"]
    assert not (tmp_path / "user-data").exists()
