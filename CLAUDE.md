# spec2md

## 하네스: 3GPP 규격 → Markdown raw 변환

**목표:** 로컬 3GPP 규격 .docx를 LLM 위키 생성 전 단계의 조항·주제별 Markdown raw 파일(영어)로 충실하게 변환한다.

**호출 조건:** 3GPP 규격 변환, 변환 도구(spec2md) 개발·수정, 변환 결과 검사, 주제별 묶음, 재변환 관련 작업을 요청받으면 `spec2md:spec2md-orchestrator` 스킬을 사용한다. 단순 질문에는 직접 답해도 된다.

## 개발 환경

이 저장소는 마켓플레이스(`spec2md`) 루트이고, `plugin/`이 플러그인이다. 로컬 마켓플레이스 플러그인은 복사되지 않고 제자리에서 로드되므로 `plugin/` 수정은 `/reload-plugins` 후 바로 반영된다. 개발용 설치:

```
claude plugin marketplace add ./
claude plugin install spec2md@spec2md --scope project
```

사용자는 clone 없이 `claude plugin marketplace add CW-Nam/spec2md`로 설치한다(README 참고). 원격 설치본은 캐시 복사본이라 `plugin/.claude-plugin/plugin.json`의 `version`을 올려야 업데이트가 내려간다. `plugin/hooks/check_deps.py`가 세션 시작 때 uv가 설치돼 있는지 확인한다.

**의존성:** uv로 관리한다. 기준은 `plugin/pyproject.toml`(런타임: lxml, olefile / `dev` 그룹: python-docx, pytest)과 `plugin/uv.lock`이고, `uv run`이 Python ≥3.11과 `plugin/.venv`를 알아서 맞춘다. 패키지 추가·변경은 `plugin/`에서 `uv add 패키지==버전`(테스트 전용은 `uv add --dev`)으로 하고 uv.lock을 함께 커밋한다. `plugin/requirements.txt`는 uv 없는 사용자를 위한 pip 대안이라 같은 버전으로 맞춰 둔다.

**명령:**
```
uv sync --project plugin                                  # 의존성 설치 (plugin/.venv)
uv run --project plugin pytest -q plugin                  # 테스트 (pytest 설정이 plugin/pyproject.toml에 있음)
uv run --project plugin spec2md batch 3gpp-specs/ -o raw/      # 일괄 변환 (--only, --depth CODE=N, --split-depth)
uv run --project plugin spec2md convert 3gpp-specs/X.docx -o raw/   # 분할 규격은 파트 파일을 모두 넘김
uv run --project plugin spec2md link raw -o linked        # 참조 링크 사본
uv run --project plugin spec2md topics raw/{spec}/        # topics/topics.json → 주제 파일
```
`--project`는 작업 폴더를 바꾸지 않으므로 `3gpp-specs/`, `raw/` 같은 상대 경로는 저장소 루트 기준이다. 검사 스크립트는 각 스킬의 `scripts/`에 있고 `uv run --project plugin python plugin/skills/.../scripts/X.py`로 실행한다 (check_output.py, check_all.py, check_links.py, check_topics.py, lint_wiki.py). 스킬·에이전트 문서의 명령은 `uv run --project "${CLAUDE_PLUGIN_ROOT}" ...` 형식을 쓴다.

**데이터 흐름:** `3gpp-specs/`(원본 docx) → `raw/`(조항 md) → `linked/`(링크 사본) → `wiki/`. 모두 gitignore 대상이다. `raw/`와 `linked/`는 생성물이라 직접 고치지 않고 재생성한다. 위키는 `linked/`만 인용한다. `_workspace/`는 에이전트 작업 파일이고 `01_analyst_*.md`만 추적한다.
출력 형식의 기준은 `plugin/skills/spec-md-conversion/references/output-contract.md`다.

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
| --- | --- | --- | --- |
| 2026-11-25 | Harness v2로 처음 구성 | 전체 | - |
| 2026-11-25 | 분할 규격(`_cover`, `_s00-07` …) 병합 규칙, 제목 해석 규칙(문자 접미 번호·번호 깊이 level·H6·오타 보정), 본문 규칙 보완(TH/TF, 파이프 표 조건, 첨자, OLE 수식 LaTeX 복원) | output-contract.md, inspect_docx.py, check_output.py, check_all.py | 첫 일괄 변환(38개 규격) 형식 분석·검사 결과 |
| 2026-11-26 | 플러그인 구조로 이동(plugin/), 경로 변수화 | 전체 | 배포·위키 확장 |
| 2026-11-26 | link 명령·spec-linking·llm-wiki 스킬·wiki-editor 에이전트 추가 | plugin/ | 참조 링크·위키 단계 |
| 2026-11-26 | 마켓플레이스 이름 spec2md-local → spec2md, SessionStart 의존성 확인 훅, 원격 설치 안내, v0.3.0 | marketplace.json, plugin/hooks/, README.md | clone 없이 GitHub에서 설치 |
| 2026-11-26 | uv로 의존성·실행 관리(uv.lock, `dev` 그룹, 스킬 명령 `uv run --project`), 훅은 uv 설치 확인, v0.4.0 | plugin/pyproject.toml, plugin/uv.lock, plugin/hooks/, 스킬·에이전트, README.md | 시스템 Python에 의존성이 없어도 스킬이 실행되게 |
| 2026-11-26 | 원본 규격 폴더 `specs/` → `3gpp-specs/` 이름 변경 (check_all.py `--specs` 기본값 포함), v0.4.1 | .gitignore, 문서·스킬·check_all.py | 폴더 용도를 이름에서 분명히 |
