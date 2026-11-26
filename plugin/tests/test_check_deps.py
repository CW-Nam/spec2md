"""hooks/check_deps.py(SessionStart uv 확인 훅) 테스트: CLI를 서브프로세스로 실행."""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "hooks", "check_deps.py")


def run(env_extra):
    env = dict(os.environ, **env_extra)
    return subprocess.run([sys.executable, SCRIPT], capture_output=True, text=True,
                          encoding="utf-8", env=env, timeout=60)


def test_silent_when_uv_present():
    # 테스트를 실행하는 Python은 PATH에 반드시 있는 실행 파일이다.
    r = run({"SPEC2MD_UV_EXE": sys.executable})
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_reports_missing_uv():
    r = run({"SPEC2MD_UV_EXE": "no_such_uv_xyz", "CLAUDE_PLUGIN_ROOT": ROOT})
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert "uv is not installed" in out["systemMessage"]
    assert "requirements.txt" in out["systemMessage"]
    ctx = out["hookSpecificOutput"]
    assert ctx["hookEventName"] == "SessionStart"
    assert "uv is not installed" in ctx["additionalContext"]
