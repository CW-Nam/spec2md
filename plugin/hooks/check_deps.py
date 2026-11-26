"""SessionStart 훅: spec2md 실행에 필요한 uv가 있는지 확인한다.

스킬·에이전트는 `uv run --project "${CLAUDE_PLUGIN_ROOT}" ...`로 스크립트를 실행한다. uv가
pyproject.toml·uv.lock에 따라 Python과 의존성(lxml, olefile …)을 플러그인 .venv에 맞춰 주므로
여기서는 uv만 확인한다. 있으면 아무것도 출력하지 않는다. 없으면 사용자에게 보일 systemMessage와
Claude에게 줄 additionalContext로 설치 방법을 알린다. 세션을 막지 않도록 항상 0으로 끝난다.
"""
import json
import os
import shutil
import sys

# 테스트에서 없는 실행 파일 이름으로 바꿔 '없음' 경로를 확인한다.
UV = os.environ.get("SPEC2MD_UV_EXE", "uv")

INSTALL_HINT = (
    'Windows: winget install --id=astral-sh.uv -e  (or: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"); '
    "macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh; "
    "or: pip install uv"
)


def main():
    if shutil.which(UV):
        return
    root = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    msg = (f"spec2md: uv is not installed (needed to run spec2md scripts). Install it - {INSTALL_HINT}. "
           f'Fallback without uv: pip install -r "{os.path.join(root, "requirements.txt")}" '
           "and run the scripts with python instead of uv run.")
    print(json.dumps({
        "systemMessage": msg,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": msg + " - spec2md scripts will fail until this is resolved; "
                                       "tell the user before running them.",
        },
    }))  # ensure_ascii 기본값: 경로에 비ASCII가 있어도 cp949 콘솔에서 깨지지 않는다


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # 훅 오류로 세션을 방해하지 않는다
        print(f"spec2md dependency check failed: {e}", file=sys.stderr)
    sys.exit(0)
