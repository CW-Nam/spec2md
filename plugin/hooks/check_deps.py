"""SessionStart 훅: spec2md 실행에 필요한 Python 버전과 모듈이 있는지 확인한다.

모두 있으면 아무것도 출력하지 않는다. 빠진 것이 있으면 사용자에게 보일 systemMessage와
Claude에게 줄 additionalContext로 설치 명령을 알린다. 세션을 막지 않도록 항상 0으로 끝난다.
"""
import importlib.util
import json
import os
import sys

MIN_PYTHON = (3, 11)
# 변환·링크 실행에 필요한 런타임 의존성 (pyproject.toml의 dependencies). python-docx, pytest는 테스트용.
DEFAULT_MODULES = "lxml,olefile"


def missing_modules(names):
    return [n for n in names if importlib.util.find_spec(n) is None]


def main():
    names = [n.strip() for n in os.environ.get("SPEC2MD_REQUIRED_MODULES", DEFAULT_MODULES).split(",")
             if n.strip()]
    problems = []
    if sys.version_info < MIN_PYTHON:
        problems.append(f"Python {sys.version.split()[0]} (needs >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]})")
    missing = missing_modules(names)
    if missing:
        problems.append("missing modules: " + ", ".join(missing))
    if not problems:
        return

    root = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    req = os.path.join(root, "requirements.txt")
    cmd = f'"{sys.executable}" -m pip install -r "{req}"'
    msg = f"spec2md: {'; '.join(problems)}. Install with: {cmd}"
    print(json.dumps({
        "systemMessage": msg,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": msg + " - spec2md scripts will fail until this is installed; "
                                       "tell the user before running them.",
        },
    }))  # ensure_ascii 기본값: 경로에 비ASCII가 있어도 cp949 콘솔에서 깨지지 않는다


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # 훅 오류로 세션을 방해하지 않는다
        print(f"spec2md dependency check failed: {e}", file=sys.stderr)
    sys.exit(0)
