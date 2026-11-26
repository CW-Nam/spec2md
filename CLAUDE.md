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

사용자는 clone 없이 `claude plugin marketplace add CW-Nam/spec2md`로 설치한다(README 참고). 원격 설치본은 캐시 복사본이라 `plugin/.claude-plugin/plugin.json`의 `version`을 올려야 업데이트가 내려간다. `plugin/hooks/check_deps.py`가 세션 시작 때 Python 버전과 런타임 의존성(lxml, olefile)을 확인한다.

**의존성:** Python ≥3.11, `pip install -r plugin/requirements.txt` (lxml, python-docx, olefile, pytest)

**명령:**
```
cd plugin && python -m pytest -q                       # 테스트 (pytest 설정이 plugin/pyproject.toml에 있음)
python plugin/scripts/spec2md.py batch specs/ -o raw/  # 일괄 변환 (--only, --depth CODE=N, --split-depth)
python plugin/scripts/spec2md.py convert specs/X.docx -o raw/   # 분할 규격은 파트 파일을 모두 넘김
python plugin/scripts/spec2md.py link raw -o linked    # 참조 링크 사본
python plugin/scripts/spec2md.py topics raw/{spec}/    # topics/topics.json → 주제 파일
```
검사 스크립트는 각 스킬의 `scripts/`에 있다 (check_output.py, check_all.py, check_links.py, check_topics.py, lint_wiki.py).

**데이터 흐름:** `specs/`(원본 docx) → `raw/`(조항 md) → `linked/`(링크 사본) → `wiki/`. 모두 gitignore 대상이다. `raw/`와 `linked/`는 생성물이라 직접 고치지 않고 재생성한다. 위키는 `linked/`만 인용한다. `_workspace/`는 에이전트 작업 파일이고 `01_analyst_*.md`만 추적한다.
출력 형식의 기준은 `plugin/skills/spec-md-conversion/references/output-contract.md`다.

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
| --- | --- | --- | --- |
| 2026-11-25 | Harness v2로 처음 구성 | 전체 | - |
| 2026-11-25 | 분할 규격(`_cover`, `_s00-07` …) 병합 규칙, 제목 해석 규칙(문자 접미 번호·번호 깊이 level·H6·오타 보정), 본문 규칙 보완(TH/TF, 파이프 표 조건, 첨자, OLE 수식 LaTeX 복원) | output-contract.md, inspect_docx.py, check_output.py, check_all.py | 첫 일괄 변환(38개 규격) 형식 분석·검사 결과 |
| 2026-11-26 | 플러그인 구조로 이동(plugin/), 경로 변수화 | 전체 | 배포·위키 확장 |
| 2026-11-26 | link 명령·spec-linking·llm-wiki 스킬·wiki-editor 에이전트 추가 | plugin/ | 참조 링크·위키 단계 |
| 2026-11-26 | 마켓플레이스 이름 spec2md-local → spec2md, SessionStart 의존성 확인 훅, 원격 설치 안내, v0.3.0 | marketplace.json, plugin/hooks/, README.md | clone 없이 GitHub에서 설치 |
