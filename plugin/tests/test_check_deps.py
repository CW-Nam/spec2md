"""hooks/check_deps.py(SessionStart 의존성 확인 훅) 테스트: CLI를 서브프로세스로 실행."""
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


def test_silent_when_all_present():
    r = run({"SPEC2MD_REQUIRED_MODULES": "json,os"})
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_reports_missing_module():
    r = run({"SPEC2MD_REQUIRED_MODULES": "json,no_such_module_xyz", "CLAUDE_PLUGIN_ROOT": ROOT})
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert "no_such_module_xyz" in out["systemMessage"]
    assert "requirements.txt" in out["systemMessage"]
    ctx = out["hookSpecificOutput"]
    assert ctx["hookEventName"] == "SessionStart"
    assert "no_such_module_xyz" in ctx["additionalContext"]
