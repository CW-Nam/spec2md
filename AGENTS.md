# spec2md 프로젝트 지침

## 목적과 데이터 흐름

- 로컬 3GPP TS/TR `.docx`를 원문에 충실한 영어 Markdown으로 변환한다. 원본은 `3gpp-specs/`, 조항별 변환본과 주제 파일은 `raw/`, 참조 링크를 붙인 사본은 `linked/`, 위키는 `wiki/`에 둔다.
- `raw/`와 `linked/`의 생성 파일은 직접 편집하지 않고 원본이나 변환 로직을 바탕으로 재생성한다. 주제 분류를 수정할 때는 `raw/{spec}/topics/topics.json`을 갱신한 뒤 `spec2md topics`를 실행한다. 위키의 출처 인용은 `linked/` 파일을 사용한다.
- `3gpp-specs/`, `raw/`, `linked/`, `wiki/`는 Git 추적 대상에서 제외한다. `_workspace/`의 작업 산출물 중 `01_analyst_*.md`만 추적 대상으로 둔다.

## 개발과 검증

- Python 소스는 `plugin/src/spec2md/`, 테스트는 `plugin/tests/`에 있다. Python 3.11 이상과 uv를 사용한다. 의존성은 `plugin/pyproject.toml`과 `plugin/uv.lock`을 기준으로 관리하고, 런타임 의존성을 바꾸면 pip 설치용 `plugin/requirements.txt`도 맞춘다.
- 명령은 저장소 루트에서 실행한다. `uv run --project plugin`은 사용할 프로젝트를 지정하며 작업 디렉터리는 유지한다.

```text
uv sync --project plugin
uv run --project plugin pytest -q plugin
uv run --project plugin spec2md batch 3gpp-specs/ -o raw/
uv run --project plugin spec2md convert 3gpp-specs/X.docx -o raw/
uv run --project plugin spec2md link raw -o linked
uv run --project plugin spec2md topics raw/{spec}/
```

- 일부 규격만 일괄 변환할 때는 `batch --only`를 사용한다. 여러 파트로 배포된 규격을 `convert`로 처리할 때는 같은 규격의 파트 파일을 모두 넘긴다.
- 출력 형식의 기준은 `plugin/skills/spec-md-conversion/references/output-contract.md`다. 출력 규약을 변경하는 작업에서는 변환기와 관련 검사기도 함께 검토한다. 변환 동작을 바꿨다면 pytest와 변경 범위에 맞는 출력 검사로 확인한다.

## 작업별 참고 문서

변환, 재변환, 검사, 참조 링크 또는 주제 묶음 요청에는 `$spec2md-orchestrator` 스킬(`.agents/skills/spec2md-orchestrator/SKILL.md`)을 사용한다. 아래 문서는 작업별 세부 규칙을 담고 있다. Claude 문서의 `${CLAUDE_PLUGIN_ROOT}`는 로컬 체크아웃의 `plugin/`, `${CLAUDE_SKILL_DIR}`는 해당 스킬의 폴더로 해석한다.

| 작업 | 참고할 `plugin/skills/` 하위 문서 | 실행 스크립트 |
| --- | --- | --- |
| DOCX 구조 분석 | `3gpp-docx-structure/SKILL.md` | `inspect_docx.py` |
| 변환 도구 개발 | `spec-md-conversion/SKILL.md` | |
| 단일 규격 변환 검사 | `conversion-check/SKILL.md` | `check_output.py` |
| 일괄 변환 검사 | `spec2md-orchestrator/SKILL.md` | `check_all.py` |
| 참조 링크 생성과 검사 | `spec-linking/SKILL.md` | `check_links.py`, `mk_unresolved.py`(검사 뒤 미해결 참조 HTML) |
| 주제 분류와 검사 | `topic-grouping/SKILL.md` | `check_topics.py` |
| 위키 작성·질의·점검 | `llm-wiki/SKILL.md` | `lint_wiki.py` |

검사 스크립트는 해당 스킬의 `scripts/`에 있다. `uv run --project plugin python plugin/skills/<스킬>/scripts/<스크립트>.py`에 작업에 필요한 인자를 붙여 실행한다. Claude Code 플러그인의 설치와 배포 절차는 `CLAUDE.md`와 `README.md`를 참고한다.
