# spec2md 플러그인 + 참조 링크 + LLM 위키 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 spec2md 도구·하네스를 `plugin/` 아래 Claude Code 플러그인으로 옮기고, raw 조항 간 참조를 링크 사본(`linked/`)으로 만드는 `spec2md link`와 Karpathy식 LLM 위키 스킬을 더한 뒤, 실데이터(38개 규격, beam failure recovery)로 끝까지 검증한다.

**Architecture:** 링크는 결정적 Python 파이프라인이다: 목적지 색인(`link_index`) → 참조 해석(`link_refs`) → 렌더링(`link_render`) → 출력·통계(`link`). 원본 `raw/`는 바꾸지 않고 `linked/`에 사본과 `refs.json`을 쓴다. 검사기(`check_links.py`, `lint_wiki.py`)는 spec2md를 import하지 않는 독립 표준 라이브러리 스크립트다(독립 오라클). 위키는 스킬·스키마·에이전트 문서와 lint 스크립트로 구성되고 LLM이 페이지를 쓴다.

**Tech Stack:** Python 3.11, lxml(변환기만), pytest, Claude Code 플러그인(skills/agents).

**Spec:** `docs/superpowers/specs/2026-11-26-spec2md-plugin-llm-wiki-design.md`

## Global Constraints

- Python `>=3.11`. 새 의존성 추가 금지. `link*.py`, `check_links.py`, `lint_wiki.py`는 표준 라이브러리만 쓴다.
- 출력 파일은 UTF-8(BOM 없음), 줄바꿈 LF(`open(..., "w", encoding="utf-8", newline="\n")`).
- 같은 입력 → 같은 출력. 실행 시각 등 실행마다 달라지는 값을 출력에 넣지 않는다. JSON은 `sort_keys=True, ensure_ascii=False, indent=1`.
- `raw/`는 절대 쓰지 않는다(예외: 기존 규약대로 topic-grouping이 만드는 `raw/{spec}/topics/`).
- 링크 경로는 항상 `/` 구분 상대 경로(`posixpath`). 역슬래시 금지. 심볼릭 링크 금지.
- 링크 형식: 표준 Markdown `[text](path#anchor)`, HTML `<table>` 안에서는 `<a href="path#anchor">text</a>`. 앵커는 별도 줄의 `<a id="..."></a>`. 앵커 id: `table-{번호}`, `figure-{번호}`, `clause-{번호}` (예: `table-8.1-2`, `clause-5.2.2.2.1`).
- 틀린 링크 금지: 모호(`ambiguous`)·대상 규격 없음(`missing_spec`)·대상 번호 없음(`missing_target`)은 링크하지 않고 `refs.json`에만 남긴다.
- 위키 페이지는 영어, query 답은 사용자 언어(한국어).
- 플러그인 이름 `spec2md`, 마켓플레이스 이름 `spec2md-local`. 플러그인 에이전트는 `spec2md:<name>`, 스킬은 `spec2md:<name>`으로 불린다.
- 플러그인 경로는 스킬·에이전트 본문에서 `${CLAUDE_PLUGIN_ROOT}`(플러그인 루트), 스킬 자기 폴더는 `${CLAUDE_SKILL_DIR}`로 쓴다. 데이터 경로(`3gpp-specs/`, `raw/`, `linked/`, `wiki/`, `_workspace/`)는 사용자 작업 폴더 기준 상대 경로다.

## Review Focus

1. **HTML 표 셀 안 참조** — `<td>` 안 `Table 8.1-2`는 `<a href>`로 감싸야 하고, 같은 셀의 `$…$`·`<br>`·태그 속성은 그대로여야 한다. → Task 4 `test_html_cell_uses_anchor_tag`.
2. **끝 구두점·문자 접미 번호** — `clause 9.1.5.`는 `9.1.5`로, `Table 5.2.2.2.1a-5`, `Table A.2-1`, `clause 4.3A`는 그 번호 그대로 해석해야 한다. → Task 3 `test_number_shapes`.
3. **본문 없는 상위 조항 참조** — manifest에서 `file: null`인 `clause 5`는 깨진 링크가 아니라 첫 하위 조항 파일로 가야 한다. → Task 2 `test_fileless_clause_points_to_first_descendant`.
4. **재실행** — 이전 실행에서 남은 `linked/{spec}/clauses/` 파일(재변환으로 사라진 조항)이 남아 있으면 안 되고, 두 번 실행 결과가 바이트 단위로 같아야 한다. → Task 5 `test_rerun_clears_stale_and_is_deterministic`.
5. **Windows 경로** — 링크·`refs.json`·`index.json`에 `\`가 섞이면 브라우저·VS Code에서 깨진다. → Task 5 `test_no_backslashes_in_outputs`.

---

## 파일 구조

```
.claude-plugin/marketplace.json            # 생성: 로컬 마켓플레이스 (source ./plugin)
plugin/
  .claude-plugin/plugin.json               # 생성
  scripts/spec2md.py                       # 생성: src/를 sys.path에 넣고 cli.main 호출
  pyproject.toml, requirements.txt         # 이동(루트 → plugin/)
  src/spec2md/                             # 이동 + 아래 신규
    link_index.py                          # 목적지 색인
    link_refs.py                           # 보호 구간 + 참조 찾기·해석
    link_render.py                         # 앵커·링크·media·역참조 렌더링
    link.py                                # run_link: 전체 실행·출력
    cli.py                                 # 수정: link 하위 명령
  tests/                                   # 이동 + 아래 신규
    raw_builder.py                         # 합성 raw 트리 생성 도우미
    test_link_index.py, test_link_refs.py, test_link_render.py, test_link.py
    test_check_links.py, test_lint_wiki.py
  agents/                                  # 이동(.claude/agents) + wiki-editor.md
  skills/                                  # 이동(.claude/skills) + 아래 신규
    spec-linking/SKILL.md, scripts/check_links.py
    llm-wiki/SKILL.md, templates/SCHEMA.md, scripts/lint_wiki.py
CLAUDE.md                                  # 수정: 개발 안내·변경 이력
```

---

## Phase A — 플러그인으로 옮기기

### Task 1: 플러그인 구조로 이동하고 경로 갱신

**Files:**
- Move (`git mv`): `src/` → `plugin/src/`, `tests/` → `plugin/tests/`, `pyproject.toml` → `plugin/pyproject.toml`, `requirements.txt` → `plugin/requirements.txt`, `.claude/skills/*` → `plugin/skills/*`, `.claude/agents/*` → `plugin/agents/*`
- Create: `plugin/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugin/scripts/spec2md.py`
- Modify: `plugin/tests/conftest.py:8-13`, 모든 `plugin/skills/*/SKILL.md`, `plugin/agents/*.md`, `plugin/skills/spec-md-conversion/references/output-contract.md`, `CLAUDE.md`
- 유지: `.claude/settings.json`, `.claude/settings.local.json`

**Interfaces:**
- Produces: `python plugin/scripts/spec2md.py <cmd> ...` = 기존 `python -m spec2md <cmd> ...`. 스킬 안에서는 `python "${CLAUDE_PLUGIN_ROOT}/scripts/spec2md.py"`.

- [ ] **Step 1: 파일 이동**

```bash
mkdir -p plugin/.claude-plugin plugin/scripts plugin/skills plugin/agents
git mv src plugin/src && git mv tests plugin/tests && git mv pyproject.toml plugin/ && git mv requirements.txt plugin/
for d in .claude/skills/*/; do git mv "$d" plugin/skills/; done
for f in .claude/agents/*.md; do git mv "$f" plugin/agents/; done
```

- [ ] **Step 2: 매니페스트 작성**

`plugin/.claude-plugin/plugin.json`: `{"name": "spec2md", "version": "0.2.0", "description": "3GPP spec .docx -> clause Markdown raw, cross-reference links, and an LLM wiki", "author": {"name": "jefre"}}`

`.claude-plugin/marketplace.json`: `{"name": "spec2md-local", "owner": {"name": "jefre"}, "plugins": [{"name": "spec2md", "source": "./plugin", "description": "3GPP spec conversion, linking and LLM wiki"}]}`

- [ ] **Step 3: 실행 스크립트 `plugin/scripts/spec2md.py`**

`os.path.dirname(__file__)/../src`를 `sys.path` 맨 앞에 넣고 `from spec2md.cli import main; raise SystemExit(main())`. lxml import 실패 시 `pip install -r <plugin>/requirements.txt` 안내를 stderr에 쓰고 종료 코드 3.

- [ ] **Step 4: `conftest.py` 경로 수정**

`ROOT`는 이제 `plugin/`이다. `INSPECT = os.path.join(ROOT, "skills", "3gpp-docx-structure", "scripts", "inspect_docx.py")`, `CHECK = os.path.join(ROOT, "skills", "conversion-check", "scripts", "check_output.py")`.

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd plugin && python -m pytest -q`
Expected: `115 passed`

- [ ] **Step 6: 스킬·에이전트 본문 경로 치환**

규칙(모든 `plugin/skills/*/SKILL.md`, `references/*.md`, `plugin/agents/*.md`):
- 자기 스킬의 `.claude/skills/<self>/...` → `${CLAUDE_SKILL_DIR}/...`
- 다른 스킬의 `.claude/skills/<name>/...` → `${CLAUDE_PLUGIN_ROOT}/skills/<name>/...` (에이전트 본문은 항상 이 형식)
- `python -m spec2md` → `python "${CLAUDE_PLUGIN_ROOT}/scripts/spec2md.py"`
- 도구 코드 경로 `src/spec2md/`, `tests/` → `${CLAUDE_PLUGIN_ROOT}/src/spec2md/`, `${CLAUDE_PLUGIN_ROOT}/tests/`. 테스트 실행은 `python -m pytest -q "${CLAUDE_PLUGIN_ROOT}/tests"`
- `subagent_type: "<agent>"` / Workflow `agentType: '<agent>'` → `spec2md:<agent>`
- 동결 해시 대상 `src/spec2md/*.py` → `${CLAUDE_PLUGIN_ROOT}/src/spec2md/*.py`
- 데이터 경로(`3gpp-specs/`, `raw/`, `_workspace/`)는 그대로.

- [ ] **Step 7: 남은 옛 경로가 없는지 확인**

Run: `grep -rnE "\.claude/(skills|agents)|python -m spec2md" plugin/ CLAUDE.md`
Expected: 출력 없음

- [ ] **Step 8: 실행 스크립트와 플러그인 검증**

Run: `python plugin/scripts/spec2md.py --help` → Expected: `convert`, `batch`, `topics` 표시
Run: `claude plugin validate ./plugin` 그리고 `claude plugin validate ./` → Expected: 오류 없음

- [ ] **Step 9: `CLAUDE.md` 갱신**

하네스 호출 문장을 "`spec2md:spec2md-orchestrator` 스킬"로 바꾸고, "## 개발 환경" 절을 추가한다: 이 저장소는 로컬 마켓플레이스 루트이며 `plugin/`이 플러그인이다. 로컬 마켓플레이스 플러그인은 복사되지 않고 제자리에서 로드되므로 `plugin/` 수정은 `/reload-plugins` 후 바로 반영된다. 설치 명령 두 줄(`claude plugin marketplace add ./`, `claude plugin install spec2md@spec2md-local --scope project`). 변경 이력 표에 `2026-11-26 | 플러그인 구조로 이동(plugin/), 경로 변수화 | 전체 | 배포·위키 확장` 행 추가.

- [ ] **Step 10: 사용자에게 설치를 요청**

설치는 프로젝트 설정(`enabledPlugins`)을 바꾸므로 실행자가 하지 않는다. 위 두 명령을 사용자에게 보여 주고 실행 후 알려 달라고 요청한다. 설치 뒤 새 세션에서 `spec2md:spec2md-orchestrator`가 스킬 목록에 보이는지 사용자와 확인한다.

- [ ] **Step 11: Commit**

```bash
git add -A plugin .claude-plugin CLAUDE.md .claude
git commit -m "refactor: spec2md를 plugin/ 아래 Claude Code 플러그인으로 이동"
```

---

## Phase B — 참조 링크

### Task 2: 목적지 색인 (`link_index.py`)

**Files:**
- Create: `plugin/src/spec2md/link_index.py`, `plugin/tests/raw_builder.py`, `plugin/tests/test_link_index.py`

**Interfaces:**
- Produces:
```python
@dataclass(frozen=True)
class Target:
    file: str              # spec 폴더 기준 posix 경로, "clauses/0010_4.2_x.md"
    anchor: str | None     # "table-4.2-1"; None = 파일 맨 위
    line: int              # 캡션·제목이 있는 줄(1부터, front matter 포함 파일 전체 기준); anchor None이면 1
    ambiguous: bool = False

@dataclass
class SpecIndex:
    code: str; spec_number: str; version: str; release: str
    clauses: dict[str, Target]; tables: dict[str, Target]; figures: dict[str, Target]
    references: dict[str, str]     # "6" -> "38.214"
    files: list[str]               # manifest 순서의 본문 파일 목록

@dataclass
class CorpusIndex:
    specs: dict[str, SpecIndex]    # code -> SpecIndex
    by_number: dict[str, str]      # "38.214" -> code (버전이 가장 높은 것)

def anchor_id(kind: str, ident: str) -> str
def build_spec_index(spec_dir: str) -> SpecIndex
def build_corpus_index(raw_root: str) -> CorpusIndex   # raw_root 아래 manifest.json이 있는 폴더 전부
```
- `tests/raw_builder.py`: `make_spec(root, code, spec_number, version, clauses) -> str` — `clauses`는 `dict(clause, title, level, parent, file, body)` 목록(`file=None`이면 본문 없음). front matter(출력 규약 3절 필수 키)와 `manifest.json`을 쓰고 spec 폴더 경로를 돌려준다.

색인 규칙: 표 캡션 줄 `^\*\*Table (번호)\s*:?` , 그림 캡션 줄 `^\*Figure (번호)\s*:?` (번호 = `[0-9A-Z][0-9A-Za-z.]*-\d+[A-Za-z]?`). 파일 안 하위 조항은 `^#{2,6} (조항번호) ` 줄 → anchor `clause-…`. 파일 첫 `# ` 제목 조항은 anchor None. 참고문헌은 clause `"2"` 파일의 `**[n]**: 3GPP T[SR] (\d{2}\.\d{3}(?:-\d+)?)`. 같은 규격에서 같은 표·그림 번호가 두 번 나오면 `ambiguous=True`. 버전 비교는 `tuple(map(int, version.split(".")))`.

- [ ] **Step 1: 실패하는 테스트 작성** (`test_link_index.py`)

합성 규격 `38213-j50`(38.213, 19.5.0): clause `2`(참고문헌 `- **[6]**: 3GPP TS 38.214: "NR; …"`), `4`(file None), `4.2`(본문에 `**Table 4.2-1: Foo $x$**`, `*Figure 4.2-1: Bar*`, `## 4.2.1 Sub`), `8.1`(`**Table 8.1-2: A**`가 두 번).

```python
def test_tables_figures_subclauses(idx):
    t = idx.tables["4.2-1"]
    assert (t.file, t.anchor) == ("clauses/0003_4.2_t.md", "table-4.2-1")
    assert idx.figures["4.2-1"].anchor == "figure-4.2-1"
    assert idx.clauses["4.2.1"].anchor == "clause-4.2.1"
    assert idx.clauses["4.2"].anchor is None

def test_fileless_clause_points_to_first_descendant(idx):
    assert idx.clauses["4"] == Target("clauses/0003_4.2_t.md", None, 1)

def test_duplicate_caption_is_ambiguous(idx):
    assert idx.tables["8.1-2"].ambiguous

def test_references(idx):
    assert idx.references["6"] == "38.214"

def test_corpus_prefers_highest_version(tmp_path):
    # 38214-j40(19.4.0), 38214-j50(19.5.0) 두 폴더
    assert build_corpus_index(str(tmp_path)).by_number["38.214"] == "38214-j50"

def test_anchor_id():
    assert anchor_id("table", "8.1-2") == "table-8.1-2"
```

- [ ] **Step 2: 실패 확인** — Run: `cd plugin && python -m pytest tests/test_link_index.py -q` → Expected: FAIL (`ModuleNotFoundError: spec2md.link_index`)
- [ ] **Step 3: `link_index.py` 구현** (위 Interfaces·규칙대로)
- [ ] **Step 4: 통과 확인** — 같은 명령 → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(link): 목적지 색인"`

### Task 3: 참조 찾기·해석 (`link_refs.py`)

**Files:**
- Create: `plugin/src/spec2md/link_refs.py`, `plugin/tests/test_link_refs.py`

**Interfaces:**
- Consumes: `Target`, `SpecIndex`, `CorpusIndex` (Task 2)
- Produces:
```python
@dataclass(frozen=True)
class Ref:
    start: int; end: int        # 감쌀 텍스트의 문자 위치(파일 전체 텍스트 기준)
    text: str                   # 감쌀 텍스트: "Table 8.1-2", 생략형이면 "5.2.2.2.1a-5", 조항이면 "clause 9.1"
    line: int                   # 1부터
    kind: str                   # "table" | "figure" | "clause"
    target_id: str              # "8.1-2", "9.1", "B"
    target_spec_number: str     # "38.213"
    target_code: str | None     # 컬렉션에 없으면 None
    status: str                 # "resolved" | "ambiguous" | "missing_spec" | "missing_target"
    target: Target | None       # resolved일 때만

def protected_spans(text: str) -> list[tuple[int, int]]
def find_refs(text: str, spec: SpecIndex, corpus: CorpusIndex) -> list[Ref]   # start 순 정렬
```

보호 구간(참조로 보지 않음): front matter, ``` 펜스 블록, `$$…$$`, `$…$`, HTML 태그 자체(`<…>` 안, 속성 값 포함), 캡션 줄(`**Table …`, `*Figure …`), 제목 줄(`#`로 시작). 참조 형태: `Table|Tables|table|tables` / `Figure|Figures` / `clause|clauses|subclause|subclauses|section|sections|Annex` + 번호; 나열 `X and Y`, `X, Y and Z`, `X or Y`(뒤 번호에 단어 생략 허용), 범위 `X to Y`는 양끝만. 규격 지시: 뒤쪽 `of|in` + (`TS nn.nnn` | `TS nn.nnn [n]` | `[n]` | `[n, TS nn.nnn]`), 앞쪽 (`TS nn.nnn [n],?` | `TS nn.nnn,?` | `[n],?` | `[n, TS nn.nnn],?`) 바로 뒤의 참조. `[n]`은 `spec.references`로 규격 번호를 얻는다. 번호 끝의 `.`/`,`는 번호에 넣지 않는다.

- [ ] **Step 1: 실패하는 테스트 작성** (Task 2 fixture 재사용: 38.213 + 38.214(`Table 5.1.2.1-2`, clause `5.1.2`, `9.1.5`) + 36.133 없음)

```python
def ids(refs): return [(r.kind, r.target_id, r.target_spec_number, r.status) for r in refs]

def test_same_spec_table(c): assert ids(find(c, "see Table 4.2-1 for")) == [("table","4.2-1","38.213","resolved")]
def test_list_and_elided(c):
    assert [r.text for r in find(c, "Tables 4.2-1 and 4.2-2")] == ["Tables 4.2-1", "4.2-2"]  # 4.2-2는 missing_target
    assert [r.target_id for r in find(c, "Table 4.2-1 and 8.1-2")] == ["4.2-1", "8.1-2"]
def test_range_ends_only(c): assert [r.target_id for r in find(c, "Tables 4.2-1 to 4.2-9")] == ["4.2-1", "4.2-9"]
def test_cross_spec_forms(c):
    for s in ["clause 5.1.2 of [6]", "clause 5.1.2 in TS 38.214 [6]", "TS 38.214 [6], clause 5.1.2",
              "[6], clause 5.1.2", "clause 5.1.2 of TS 38.214", "[6, TS 38.214], clause 5.1.2"]:
        assert ids(find(c, s)) == [("clause","5.1.2","38.214","resolved")], s
def test_number_shapes(c):
    assert find(c, "in TS 38.214 [6] clause 9.1.5.")[0].target_id == "9.1.5"
    assert [r.target_id for r in find(c, "Table 5.2.2.2.1a-5, Table A.2-1, clause 4.3A")] == ["5.2.2.2.1a-5","A.2-1","4.3A"]
def test_missing_spec(c): assert ids(find(c, "clause 9.1 of TS 36.133"))[0][3] == "missing_spec"
def test_ambiguous(c): assert find(c, "Table 8.1-2")[0].status == "ambiguous"
def test_protected(c):
    for s in ["```text\nTable 4.2-1\n```", "$Table 4.2-1$", "**Table 4.2-1: caption**", "## 4.2 Table 4.2-1",
              '<img alt="Table 4.2-1">']:
        assert find(c, s) == [], s
def test_annex(c): assert ids(find(c, "see Annex B"))[0][:2] == ("clause", "B")
```
(`find(c, s)`는 `find_refs(s, c.specs["38213-j50"], c)` 도우미.)

- [ ] **Step 2: 실패 확인** — `python -m pytest tests/test_link_refs.py -q` → FAIL
- [ ] **Step 3: `link_refs.py` 구현**
- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(link): 참조 찾기와 해석"`

### Task 4: 렌더링 (`link_render.py`)

**Files:**
- Create: `plugin/src/spec2md/link_render.py`, `plugin/tests/test_link_render.py`

**Interfaces:**
- Consumes: `Ref`, `Target`, `SpecIndex` (Task 2–3)
- Produces:
```python
@dataclass(frozen=True)
class Backlink:
    from_code: str; from_spec_number: str; from_file: str; from_clause: str
    text: str                  # 참조 텍스트
    target_anchor: str | None  # 이 파일 안의 어느 목적지를 가리키는지

def href(from_code: str, from_file: str, to_code: str, target: Target) -> str
    # 같은 규격: "0123_8.1_x.md#table-8.1-2"; 다른 규격: "../../38214-j50/clauses/x.md#…"; anchor None이면 "#" 없음
def render(text: str, refs: list[Ref], spec: SpecIndex, from_file: str,
           media_prefix: str, backlinks: list[Backlink]) -> str
```

`render` 동작: (1) `spec`의 목적지 중 `file == from_file`이고 anchor가 있고 `ambiguous`가 아닌 것마다 그 `line` 바로 앞에 `<a id="{anchor}"></a>` 한 줄을 넣는다. (2) `status == "resolved"`인 참조만 감싼다. 참조 위치가 HTML `<table>…</table>` 안이면 `<a href="…">text</a>`, 아니면 `[text](…)`. (3) `](../media/`와 `src="../media/`를 `media_prefix`로 바꾼다. (4) `backlinks`가 있으면 끝에 아래 형식을 붙인다(정렬: from_spec_number, from_file, text; 같은 (from_file, target_anchor, text)는 하나만).

```
<!-- spec2md:backlinks -->
## Referenced by

- [TS 38.321 5.17](../../38321-j40/clauses/0123_5.17_x.md) — Table 8.1-2
```

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_markdown_link_and_anchor(...):
    out = render(text, refs, spec, "clauses/0003_4.2_t.md", "../../../raw/38213-j50/media/", [])
    assert '<a id="table-4.2-1"></a>\n**Table 4.2-1: Foo $x$**' in out
    assert "see [Table 4.2-1](0003_4.2_t.md#table-4.2-1) for" in out
def test_cross_spec_href():
    assert href("38213-j50", "clauses/a.md", "38214-j50", Target("clauses/b.md", "clause-5.1.2", 9)) == "../../38214-j50/clauses/b.md#clause-5.1.2"
def test_html_cell_uses_anchor_tag(...):
    # 입력 셀: '<td>see Table 4.2-1<br>$a<b$</td>'
    assert '<td>see <a href="0003_4.2_t.md#table-4.2-1">Table 4.2-1</a><br>$a<b$</td>' in out
def test_unresolved_not_linked(...): assert "Table 4.2-9" in out and "](" not in line_of(out, "4.2-9")
def test_media_rewrite(...):
    assert "![Figure](../../../raw/38213-j50/media/image1.png)" in out
    assert 'src="../../../raw/38213-j50/media/image2.emf"' in out
def test_backlinks_section(...):
    assert out.endswith("<!-- spec2md:backlinks -->\n## Referenced by\n\n- [TS 38.321 5.17](../../38321-j40/clauses/0123_5.17_x.md) — Table 8.1-2\n")
```

- [ ] **Step 2: 실패 확인** — `python -m pytest tests/test_link_render.py -q` → FAIL
- [ ] **Step 3: `link_render.py` 구현**
- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(link): 앵커·링크·역참조 렌더링"`

### Task 5: 전체 실행과 CLI (`link.py`, `cli.py`)

**Files:**
- Create: `plugin/src/spec2md/link.py`, `plugin/tests/test_link.py`
- Modify: `plugin/src/spec2md/cli.py` (하위 명령 `link`)

**Interfaces:**
- Consumes: Task 2–4 전부
- Produces:
```python
@dataclass
class LinkStats:
    specs: int; files: int
    refs: dict[str, int]        # status -> 개수
def run_link(raw_root: str, out_root: str, only: set[str] | None = None) -> LinkStats
```
- CLI: `spec2md link RAW -o OUT [--only CODE,CODE]` (기본 `RAW=raw`, `OUT=linked`). 끝에 규격별 status 개수를 stderr에 출력. 종료 코드 0.

출력(설계 5.2): `OUT/index.json`(code → `{spec_number, version, release, clauses|tables|figures: {id: {file, anchor}}}`, ambiguous 항목은 `{"ambiguous": true}`), `OUT/{code}/manifest.json`(raw manifest + `"link": {"refs": {status: n}}`), `OUT/{code}/refs.json`(`{"spec", "version", "refs": [{from_file, from_clause, line, text, kind, target_spec, target_id, target_file, anchor, status}]}`; `target_spec`은 규격 번호, 정렬 (from_file, line, start)), `OUT/{code}/clauses/*.md`. 쓰기 전에 `OUT/{code}/`를 지운다(`OUT` 안인지 확인 후). 참조·역참조는 항상 전체 코퍼스로 계산하고, `only`는 어느 규격 폴더를 쓸지만 정한다(다른 규격의 역참조 절은 갱신되지 않음을 stderr에 경고). `media_prefix = posixpath.relpath(raw/{code}/media, OUT/{code}/clauses) + "/"`.

- [ ] **Step 1: 실패하는 테스트 작성** (raw_builder로 두 규격 생성 → `run_link`)

```python
def test_end_to_end(tmp_path):
    stats = run_link(raw, out)
    assert stats.refs["resolved"] >= 3
    assert os.path.exists(f"{out}/index.json") and os.path.exists(f"{out}/38213-j50/refs.json")
    text = read(f"{out}/38214-j50/clauses/....md")
    assert "## Referenced by" in text          # 38.213에서 온 역참조
def test_raw_untouched(tmp_path): assert snapshot(raw) == before
def test_rerun_clears_stale_and_is_deterministic(tmp_path):
    run_link(raw, out); open(f"{out}/38213-j50/clauses/9999_stale.md","w").close()
    run_link(raw, out); a = snapshot(out); run_link(raw, out)
    assert not os.path.exists(f"{out}/38213-j50/clauses/9999_stale.md") and snapshot(out) == a
def test_no_backslashes_in_outputs(tmp_path):
    assert all("\\" not in read(p) for p in glob(f"{out}/**/*.json", recursive=True))
    assert "\\" not in "".join(re.findall(r"\]\(([^)]*)\)", read_all_md(out)))
def test_only(tmp_path):
    run_link(raw, out, only={"38213-j50"}); assert not os.path.exists(f"{out}/38214-j50")
def test_cli(tmp_path): assert main(["link", raw, "-o", out]) == 0
```

- [ ] **Step 2: 실패 확인** — `python -m pytest tests/test_link.py -q` → FAIL
- [ ] **Step 3: `link.py`와 CLI 구현**
- [ ] **Step 4: 통과 확인 + 전체 회귀** — `python -m pytest -q` → 전부 PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(link): spec2md link 명령"`

### Task 6: 링크 검사기와 spec-linking 스킬, 오케스트레이터 3.5단계

**Files:**
- Create: `plugin/skills/spec-linking/scripts/check_links.py`, `plugin/skills/spec-linking/SKILL.md`, `plugin/tests/test_check_links.py`
- Modify: `plugin/skills/spec2md-orchestrator/SKILL.md` (3단계 뒤 3.5단계, 경로 규칙 표에 `linked/`), `plugin/skills/spec-md-conversion/references/output-contract.md` (7절 "linked/ 출력" 추가: 5.2의 출력·앵커·링크 형식 요약)

**Interfaces:**
- CLI: `python check_links.py LINKED --raw RAW [--json OUT.json]`. 표준 라이브러리만, spec2md import 금지.
- 종료 코드: ERROR가 있으면 1, 없으면 0.
- 검사: (ERROR) 모든 `.md` 링크·`<a href>`의 파일이 존재하고 `#anchor`가 그 파일의 `<a id="…">`로 존재; (ERROR) 사본에서 앵커 줄·링크·역참조 절(`<!-- spec2md:backlinks -->` 이후)·media 접두사를 되돌리면 raw 파일과 바이트 단위로 같음; (ERROR) raw에 있는 본문 파일이 linked에 모두 있음; (WARN) 규격별 status 분포와 `missing_target` 상위 20개 `(target_spec, kind, target_id, 개수)`.

- [ ] **Step 1: 실패하는 테스트 작성** — Task 5 출력을 만든 뒤 (a) 그대로 → 종료 코드 0, (b) 앵커 하나 지움 → 1이고 출력에 `broken anchor`, (c) 사본 본문 한 글자 바꿈 → 1이고 `differs from raw`, (d) 사본 파일 하나 삭제 → 1이고 `missing`.
- [ ] **Step 2: 실패 확인** — `python -m pytest tests/test_check_links.py -q` → FAIL
- [ ] **Step 3: `check_links.py` 구현**
- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: `spec-linking/SKILL.md` 작성** — frontmatter `name: spec-linking`, description(언제: "링크 만들어줘", "참조 링크", "linked 다시", 재변환 후 링크 갱신, 해석 실패 개선). 본문: 실행 명령(`python "${CLAUDE_PLUGIN_ROOT}/scripts/spec2md.py" link raw -o linked`), 검사 명령(`python "${CLAUDE_SKILL_DIR}/scripts/check_links.py" linked --raw raw --json _workspace/05_link_check.json`), 출력 규약 7절 링크, 해석 규칙 개선 절차(검사기 WARN 상위 `missing_target`을 원문에서 확인 → 진짜 없는 번호인지, 해석 패턴 누락인지 구분 → 누락이면 `test_link_refs.py`에 실제 문장으로 실패 테스트를 먼저 추가한 뒤 고침), 금지 사항(raw 수정 금지, 추측 링크 금지).
- [ ] **Step 6: 오케스트레이터 갱신** — 3단계 다음에 "3.5단계: 링크" (메인 직접 실행: link → check_links; ERROR면 converter-developer에 진단 위임) 추가, 0단계 분류표에 "링크만 다시" 행, "위키 만들어줘/질문"은 `spec2md:llm-wiki`로 넘긴다는 행 추가.
- [ ] **Step 7: Commit** — `git commit -m "feat(link): 링크 검사기와 spec-linking 스킬"`

---

## Phase C — LLM 위키

### Task 7: 위키 lint 스크립트 (`lint_wiki.py`)

**Files:**
- Create: `plugin/skills/llm-wiki/scripts/lint_wiki.py`, `plugin/tests/test_lint_wiki.py`

**Interfaces:**
- CLI: `python lint_wiki.py WIKI [--json OUT.json]`. 표준 라이브러리만. 종료 코드: ERROR 있으면 1.
- 페이지 = `WIKI/**/*.md` 중 `SCHEMA.md`, `index.md`, `log.md` 제외.
- ERROR: 깨진 상대 링크(파일 없음, 또는 `#anchor`가 대상 파일의 `<a id>`·자동 제목 slug에 없음); front matter 필수 키(`type`, `title`, `sources`, `specs`, `updated`) 누락; `sources`가 빈 배열; `type`이 `feature|concept|spec|answer` 밖; `index.md`에 링크가 없는 페이지; `log.md`에서 `## [`로 시작하지만 `^## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint) \| .+$`에 맞지 않는 줄.
- WARN: 다른 위키 페이지에서 들어오는 링크가 없는 고아 페이지(index 링크는 세지 않음); 출처 링크(`linked/`로 가는 링크)가 하나도 없는 본문 문단이 5개 이상인 페이지.

- [ ] **Step 1: 실패하는 테스트 작성** — tmp에 `linked/38321-j40/clauses/a.md`(`<a id="table-7.1-1"></a>`)와 정상 위키(페이지 2개가 서로 링크, index·log 정상)를 만들어 → 0. 그 뒤 각각 한 가지만 깨서 → 1과 메시지 확인: `broken link`(앵커 오타), `missing front matter key: sources`, `not in index`, `bad log entry`. 고아 페이지만 있으면 → 0이고 출력에 `orphan`.
- [ ] **Step 2: 실패 확인** — `python -m pytest tests/test_lint_wiki.py -q` → FAIL
- [ ] **Step 3: `lint_wiki.py` 구현**
- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(wiki): lint_wiki 검사 스크립트"`

### Task 8: llm-wiki 스킬, 스키마 템플릿, wiki-editor 에이전트

**Files:**
- Create: `plugin/skills/llm-wiki/SKILL.md`, `plugin/skills/llm-wiki/templates/SCHEMA.md`, `plugin/agents/wiki-editor.md`

**Interfaces:**
- `llm-wiki` 스킬이 부르는 것: `lint_wiki.py`(Task 7), `linked/{spec}/refs.json`·`index.json`(Task 5), `raw/{spec}/topics/`(기존 topic-grouping).
- 일괄 ingest 제안 파일 형식 `_workspace/wiki/{spec}_{topic}.json`: `{"spec", "topic", "pages": [{"path": "features/x.md", "action": "create|update", "type", "title", "content_md", "sources": [...]}], "log": "…"}`.

- [ ] **Step 1: `templates/SCHEMA.md`** (영어) — 설계 5.3을 위키 규칙으로 옮긴다: 세 층과 쓰기 권한, 폴더(`features/`, `concepts/`, `specs/`, `answers/`), 페이지 front matter(필수 키·한 줄 스칼라·JSON 배열 `sources`/`specs`/`related`, `specs` 원소는 `"TS 38.321 19.4.0"` 형식), 서술 문장마다 `linked/` 출처 링크, 원문 표·수식은 복사하지 않고 링크, `> CONFLICT:` 블록, 파일 이름 kebab-case, index.md 형식(종류별 `## Features` 등, 줄마다 `- [Title](features/x.md) — one-line summary (specs: 38.321, 38.331; sources: 7)`), log.md 형식(`## [YYYY-MM-DD] ingest | 38.321 beam-failure-recovery`), ingest·query·lint 절차 요약.
- [ ] **Step 2: `SKILL.md`** — frontmatter `name: llm-wiki`, description(언제: "위키 만들어줘", "위키에 넣어줘(ingest)", "○○ 기능 관련 내용 다 알려줘", "위키 점검(lint)", 위키 기반 질문; 변환·링크 자체는 다른 스킬). 본문:
  - 시작: `wiki/SCHEMA.md`가 없으면 `${CLAUDE_SKILL_DIR}/templates/SCHEMA.md`를 복사하고 빈 `index.md`·`log.md`를 만든다. 있으면 항상 먼저 읽는다. `linked/`가 없으면 spec-linking을 먼저 실행하라고 안내하고 멈춘다.
  - ingest: 설계 5.3 단계 1–4. 관련 내용 찾기 = 주제 조항의 `refs.json` 나가는 참조 + 대상 파일의 `## Referenced by`(들어오는 참조)를 한 단계 따라가 다른 규격 조항을 확인. 기본 대화형(핵심 3–5줄 보고 후 방향 확인), "일괄로"면 묻지 않음.
  - 일괄 ingest: 주제마다 읽기 에이전트(`spec2md:wiki-editor`, 제안 모드)를 병렬로 돌려 제안 JSON만 쓰게 하고, 다 끝나면 `spec2md:wiki-editor` 하나(반영 모드)가 순서대로 반영. 동시 실행 상한 5.
  - query: 설계 5.3 query 1–4. 답은 사용자 언어, 출처 링크 포함, "위키에서" / "linked에서 직접 찾음" 구분, `answers/` 저장은 사용자에게 묻고.
  - lint: `python "${CLAUDE_SKILL_DIR}/scripts/lint_wiki.py" wiki --json _workspace/06_wiki_lint.json` → ERROR 고침 → LLM 점검 항목(모순, 페이지 없는 개념, 빠진 교차 링크, ingest 후보) 보고 → log에 `lint` 항목.
  - 매 작업 끝: index.md·log.md 갱신 후 lint 스크립트 실행, ERROR 0 확인.
- [ ] **Step 3: `agents/wiki-editor.md`** — 기존 `topic-curator.md` 형식. frontmatter `name: wiki-editor`, description, `tools: Read, Grep, Glob, Bash, Write, Edit`, `model: opus`(종합·서술 품질이 핵심). 역할: llm-wiki 스킬과 `wiki/SCHEMA.md`를 따라 페이지를 쓴다. 두 모드(제안 모드: `_workspace/wiki/…json`만 씀, 위키 파일 수정 금지 / 반영 모드: 제안을 위키에 반영). 원칙: 출처 없는 서술 금지, raw·linked 수정 금지, 원문 표 복사 금지, 끝나면 lint 실행.
- [ ] **Step 4: 검증** — Run: `claude plugin validate ./plugin` → 오류 없음. Run: `grep -n "CLAUDE_SKILL_DIR\|CLAUDE_PLUGIN_ROOT" plugin/skills/llm-wiki/SKILL.md` → lint·템플릿 경로가 변수로 쓰였는지 확인.
- [ ] **Step 5: Commit** — `git commit -m "feat(wiki): llm-wiki 스킬, 스키마 템플릿, wiki-editor 에이전트"`

---

## Phase D — 실데이터 검증

이 단계는 플러그인 스킬을 실제로 쓰는 단계다. Task 1 Step 10의 설치가 끝났어야 한다.

### Task 9: 38개 규격 전체 링크와 해석 규칙 다듬기

**Files:**
- Modify(필요 시): `plugin/src/spec2md/link_refs.py`, `plugin/src/spec2md/link_index.py`, 해당 테스트
- Create: `_workspace/05_link_report.md`

- [ ] **Step 1: 실행** — Run: `python plugin/scripts/spec2md.py link raw -o linked` → 종료 코드 0, 38개 규격 통계 출력
- [ ] **Step 2: 검사** — Run: `python plugin/skills/spec-linking/scripts/check_links.py linked --raw raw --json _workspace/05_link_check.json` → Expected: ERROR 0. ERROR가 있으면 superpowers:systematic-debugging으로 원인을 찾고, 실패를 재현하는 테스트를 먼저 추가한 뒤 고친다.
- [ ] **Step 3: 해석 실패 상위 원인 검토** — WARN의 `missing_target` 상위 20개와 `ambiguous` 전부를 원문에서 확인해 (a) 원문에 실제로 없는 번호, (b) 패턴 누락, (c) 색인 누락(캡션 형식 변형)으로 나눈다. (b)(c)마다 실제 문장을 `test_link_refs.py`/`test_link_index.py`에 실패 테스트로 추가 → 고침 → `python -m pytest -q` PASS → Step 1–2 반복. 상한 3회. resolved 비율이 회차마다 오르지 않으면 멈추고 보고.
- [ ] **Step 4: 표본 확인** — 무작위 링크 10개(같은 규격 표 4, 규격 간 조항 4, HTML 셀 안 2)를 열어 목적지가 맞는지 사람 눈으로 확인하고 결과를 보고서에 적는다.
- [ ] **Step 5: 보고서** — `_workspace/05_link_report.md`: 규격별 status 분포, 회차별 resolved 비율, 고친 패턴, 남은 실패 유형과 정상으로 본 이유, 표본 확인 결과.
- [ ] **Step 6: Commit** — 코드·테스트 변경만 커밋(`linked/`, `_workspace/`는 무시됨): `git commit -m "fix(link): 실데이터 기반 해석 규칙 보완"`

### Task 10: 38.213 · 38.321 · 38.331 주제 묶음

- [ ] **Step 1:** 세 규격에 한 메시지에서 병렬로 `Agent(subagent_type: "spec2md:topic-curator", prompt: "topic-grouping 스킬로 raw/{code}/topics/topics.json을 작성하고 check_topics.py로 확인하라")` (code = `38213-j50`, `38321-j40`, `38331-j40`)
- [ ] **Step 2:** 각각 Run: `python "plugin/skills/topic-grouping/scripts/check_topics.py" raw/{code}` → 종료 코드 0
- [ ] **Step 3:** 각각 Run: `python plugin/scripts/spec2md.py topics raw/{code}` → `wrote N topic files`
- [ ] **Step 4:** beam failure recovery 관련 주제 id를 세 규격에서 찾아 목록으로 적는다(예상: 38.213 link recovery 절차, 38.321 BFD/BFR, 38.331 BFR 설정 IE). 해당 주제가 없으면 topic-curator에 그 주제만 고치게 다시 지시한다.

### Task 11: 위키 초기화와 BFR ingest

- [ ] **Step 1:** `spec2md:llm-wiki` 스킬로 위키를 초기화한다 → `wiki/SCHEMA.md`, `wiki/index.md`, `wiki/log.md` 생성 확인.
- [ ] **Step 2:** Task 10 Step 4의 주제를 대화형 ingest로 하나씩 넣는다. 주제마다 핵심 3–5줄을 사용자에게 보고하고 방향을 받는다.
- [ ] **Step 3:** Run: `python plugin/skills/llm-wiki/scripts/lint_wiki.py wiki` → Expected: ERROR 0. 최소 `features/beam-failure-recovery.md` 1개와 관련 concept 페이지가 있고, 그 `sources`에 세 규격이 모두 들어 있다.
- [ ] **Step 4:** 위키를 git으로 추적할지 사용자에게 묻고(설계: 사용자 선택), 답에 따라 `.gitignore`에 `/wiki/`를 넣거나 커밋한다.

### Task 12: query 수용 검사와 마무리

- [ ] **Step 1:** 새 대화 맥락(서브에이전트)에서 `spec2md:llm-wiki` 스킬로 "beam failure recovery 관련 내용 다 알려줘"를 질의한다. 합격 기준: 답이 위키 페이지에서 출발하고, 38.213·38.321·38.331의 조항·표를 출처 링크로 짚으며, 한국어로 답한다.
- [ ] **Step 2:** 답에 나온 링크를 전부 추출해 파일·앵커 존재를 확인한다(lint_wiki의 링크 검사 함수를 재사용하거나 같은 규칙으로). 깨진 링크 0.
- [ ] **Step 3:** 답을 `answers/`에 저장할지 사용자에게 묻고, 저장하면 index·log 갱신 후 lint ERROR 0 확인.
- [ ] **Step 4:** `CLAUDE.md` 변경 이력에 `2026-11-26 | link 명령·spec-linking·llm-wiki 스킬·wiki-editor 에이전트 추가 | plugin/ | 참조 링크·위키 단계` 행 추가, 플러그인 `version`은 `0.2.0` 유지.
- [ ] **Step 5:** 전체 회귀 — Run: `cd plugin && python -m pytest -q` → 전부 PASS. Run: `claude plugin validate ./plugin` → 오류 없음.
- [ ] **Step 6: Commit** — `git commit -m "docs: 플러그인·링크·위키 변경 이력"`
