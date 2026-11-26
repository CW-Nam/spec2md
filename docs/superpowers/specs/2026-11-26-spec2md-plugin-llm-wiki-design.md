# spec2md 플러그인화 + 참조 링크 + LLM 위키 설계

- 날짜: 2026-11-26
- 상태: 초안(사용자 승인 대기)
- 참고: Karpathy, "LLM Wiki" (https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

## 1. 의도

3GPP 규격(TS 36/38/24 계열, 현재 38개, 모두 Rel-19)을 docx → 조항별 Markdown raw로 바꾸는 기존 도구·하네스(`spec2md`)를 **하나의 Claude Code 플러그인**으로 묶고, 그 위에 두 기능을 더한다.

1. **raw 파일 간 참조 링크.** 규격 본문은 표(`Table 8.1-2`), 조항(`clause 5.3.5`), 다른 규격(`TS 38.214 [6], clause 9.1.5`, `[2, TS 36.331]`)을 매우 많이 참조한다(38개 규격 기준 대략 표 참조 39,500, 조항 참조 14,400, 규격 간 참조 3,500). 이 참조를 클릭 가능한 링크로 만들고, 같은 링크 데이터로 나중에 웹페이지를 만들 수 있게 한다.
2. **LLM 위키.** Karpathy 패턴으로 위키를 쌓는다. 특정 기능(예: beam failure recovery, DRX, handover)에 대한 질문에 여러 규격에 흩어진 관련 내용을 모두 찾아 출처 링크와 함께 답하는 것이 목적이다.

왜: 한 기능이 RRC(38.331)·MAC(38.321)·물리계층(38.213/214)·요구사항(38.133)에 흩어져 있고, 그 사이를 사람이 표 번호와 조항 번호로 손수 따라가야 한다. 링크는 이 추적을 기계화하고, 위키는 추적 결과를 기능 단위로 누적한다.

## 2. 목표 · 비목표 · 반목표

**목표**
- 기존 에이전트 5개·스킬 5개·Python 패키지를 플러그인 하나로 배포 가능하게 한다.
- `spec2md link`: 결정적(같은 입력 → 같은 출력) 참조 해석과 링크 사본 생성. 해석 실패를 숨기지 않고 집계한다.
- `llm-wiki` 스킬: ingest / query / lint 세 작업과 위키 스키마.
- 성공 기준: "beam failure recovery 관련 내용 다 알려줘"에 대해 38.213·38.321·38.331의 해당 조항과 표를 링크로 짚어 답하고, 그 링크가 **VS Code Markdown 미리보기와 브라우저에서** 실제 조항·표 위치로 열린다. 답은 `linked/` grep 대체 경로가 아니라 ingest된 위키 페이지에서 나와야 한다.
- **실데이터 검증까지 이번 범위다(사용자 결정 2026-11-26).** 38개 규격 전체에 `spec2md link`를 돌려 `check_links.py`의 ERROR를 0으로 만들고, `missing_target`·`ambiguous` 상위 원인을 보고 해석 규칙을 다듬는다. 이어서 38.213·38.321·38.331을 주제로 묶고, beam failure recovery 관련 주제를 위키에 ingest한 뒤, 위 질문으로 query를 해 본다.

**비목표(이번 범위 밖)**
- 같은 규격의 Release 간 변화 추적. **나중에 결정한다(사용자 결정 2026-11-26).** 다만 위키 페이지와 `refs.json`이 출처의 `version`·`release`를 항상 기록해 나중에 붙일 수 있게 한다.
- 웹페이지 생성기 자체. 이번에는 웹페이지가 쓸 데이터(`refs.json`, 앵커가 있는 링크 사본)까지만 만든다.
- 규격 내용의 기술적 정확성 검증.
- 임베딩/벡터 검색 인프라. `index.md` + grep + 역참조로 시작한다(Karpathy: 중간 규모에서는 index로 충분).

**반목표(기술적으로 돌아가도 실패로 보는 것)**
- raw 원본(`raw/{spec}/clauses/*.md`)을 고치는 것. raw는 불변 출처층이다.
- 해석하지 못한 참조를 엉뚱한 표·조항에 링크하는 것. 틀린 링크는 링크가 없는 것보다 나쁘다. 모호하면 링크하지 않고 `refs.json`에 `ambiguous`로 남긴다.
- 출처 링크 없이 LLM이 지어낸 서술이 위키에 들어가는 것.

## 3. 제약

- Windows 11, PowerShell 기본 + Git Bash. Python 3.11, 의존성 `lxml`만.
- 기존 출력 규약(`spec-md-conversion/references/output-contract.md`)과 재현성 원칙(실행마다 달라지는 필드 금지)을 따른다.
- 데이터 폴더(`3gpp-specs/`, `raw/`, `linked/`, `wiki/`, `_workspace/`)는 **사용자 작업 폴더**에 있고 플러그인 안에 있지 않다. 플러그인은 도구·스킬·에이전트만 담는다.
- raw는 GFM 파이프 표와 HTML `<table>`이 섞여 있다. 표 제목은 `**Table 4.1-1: …**` 한 줄(TH 규칙)로 표 앞에 온다. 제목 안에 LaTeX가 들어 있는 경우가 있어 GFM 자동 slug 앵커는 믿을 수 없다.
- **링크 뷰어는 VS Code 미리보기·브라우저다(사용자 결정).** 표준 Markdown 상대 링크 + HTML `<a id>` 앵커를 쓴다. Obsidian 위키링크·블록 참조 형식은 만들지 않는다(Obsidian에서는 파일까지만 열린다). 나중의 웹페이지도 같은 형식을 그대로 쓴다. 심볼릭 링크에 기대지 않는다(Windows·브라우저 호환).
- **위키 페이지 언어는 영어다(사용자 결정).** raw와 같은 언어라 IE·타이머 이름 검색과 원문 대조가 맞는다. query 답은 사용자 언어(한국어)로 준다.
- 분할 깊이보다 깊은 조항은 파일 안의 `##`~`######` 제목이다(`## 5.2.2.2.1 SIB validity`). 조항 참조의 목적지는 파일 + 파일 안 위치여야 한다.

## 4. 접근 방식 (검토한 안)

| 안 | 내용 | 장단점 |
| --- | --- | --- |
| A | raw 파일 안에 직접 링크를 넣는다 | 단순, 즉시 클릭 가능. 그러나 raw 불변 원칙 위반, 재변환마다 링크 재작업, 원문 diff 오염 |
| **B (선택)** | 링크 그래프 `refs.json`을 원천 데이터로 두고, 링크·앵커·역참조를 넣은 **사본** `linked/`를 생성 | raw 불변 유지, 웹페이지·위키가 같은 그래프 사용, 해석 실패 집계 가능. 대가는 디스크 사본 한 벌 |
| C | `refs.json`만 만들고 파일은 그대로 | 가장 가벼우나 웹페이지 전까지 링크를 따라갈 수 없음 |

**사용자 선택: B (2026-11-26).**

## 5. 설계

### 5.1 플러그인 구조

플러그인은 저장소 안 **`plugin/` 하위 폴더**에 둔다. 저장소 루트는 작업 폴더로 남는다(설계자 결정). 이유: `3gpp-specs/`(278 MB)·`raw/`(252 MB)·`_workspace/`(52 MB)가 루트에 있어 루트를 플러그인으로 삼으면 설치 시 캐시로 함께 복사된다. 데이터 580 MB를 옮기는 대신 코드(수 MB)를 옮긴다.

```
spec2md/                         # 저장소 루트 = 작업 폴더 (데이터는 여기 그대로)
├── .claude-plugin/
│   └── marketplace.json         # 로컬 마켓플레이스: plugins[0].source = "./plugin"
├── plugin/                      # 플러그인 루트
│   ├── .claude-plugin/plugin.json   # name: "spec2md", version: "0.2.0"
│   ├── agents/                  # ← .claude/agents/* 이동 + wiki-editor 추가
│   ├── skills/                  # ← .claude/skills/* 이동 + spec-linking, llm-wiki 추가
│   │   ├── spec-linking/
│   │   └── llm-wiki/
│   │       ├── SKILL.md
│   │       ├── templates/SCHEMA.md  # 위키 스키마 초기본
│   │       └── scripts/lint_wiki.py
│   ├── scripts/spec2md.py       # 실행 스크립트 (아래)
│   ├── src/spec2md/             # Python 패키지(기존) + link.py 추가
│   ├── tests/
│   └── pyproject.toml
├── 3gpp-specs/ raw/ linked/ wiki/ _workspace/   # 데이터 (gitignore, wiki/는 추적 여부 사용자 선택)
├── docs/
└── CLAUDE.md                    # 이 저장소에서 플러그인을 개발할 때의 안내
```

- **개발 루프:** 이 저장소에서 개발할 때는 설치본(캐시 사본)이 아니라 `claude --plugin-dir ./plugin`처럼 작업 사본을 직접 불러 쓴다. 그래서 converter-developer가 `plugin/src/spec2md/`를 고치면 바로 반영된다. 이 방법이 실제로 되는지는 구현 첫 단계에서 Claude Code 문서로 확인하고, 안 되면 대안을 보고한다. 변환 도구 개발 에이전트·스킬은 배포 플러그인에도 그대로 남긴다(다른 사용자가 새 Release 형식에 맞춰 고칠 수 있게).

- 스킬·에이전트 안의 스크립트 경로(`.claude/skills/.../check_output.py` 등)는 플러그인 루트 기준 경로로 바꾼다. 스킬 본문에서 플러그인 루트를 가리키는 방법(`${CLAUDE_PLUGIN_ROOT}` 치환 여부 등)은 구현 전에 Claude Code 문서로 확인한다. 치환이 안 되면 스킬 디렉터리 기준 상대 경로를 쓴다.
- Python 도구 실행: 플러그인 안 `src/`를 `sys.path`에 넣고 `spec2md.cli.main`을 부르는 작은 실행 스크립트(`scripts/spec2md.py`)를 두고, 스킬은 이것을 부른다. `pip install` 없이 동작하게 하기 위해서다(lxml만 설치돼 있으면 됨). lxml이 없으면 스킬이 설치를 안내한다.
- `.claude/` 아래 기존 사본은 지운다. 중복 정의로 같은 스킬이 두 번 뜨는 것을 막기 위해서다.
- 프로젝트 `CLAUDE.md`의 하네스 설명(오케스트레이터 호출 조건)은 플러그인 쪽 스킬 description으로 옮기고, 저장소 `CLAUDE.md`에는 개발 안내와 변경 이력만 남긴다.

### 5.2 참조 링크 (`spec2md link`, 스킬 `spec-linking`)

**명령**: `spec2md link raw/ -o linked/` — 규격 간 참조를 풀어야 하므로 raw 전체를 한 번에 처리한다. `--only`로 일부 규격만 다시 만들 수 있게 하되, 목적지 색인은 항상 전체 raw에서 만든다.

**1단계 — 목적지 색인.** 규격마다:
- 조항: `manifest.json`의 조항 + 각 파일 안 `##`~`######` 번호 제목 → (파일, 앵커).
- 표: `**Table X-Y: …**`/`**Table X-Y:**` 줄 → (파일, 앵커). 그림(`*Figure X-Y: …*`)도 같은 방식으로 색인한다(비용이 거의 같다).
- 참고문헌: 조항 2(References)의 `**[n]**: 3GPP TS 38.214: …` → `[n] → 38.214`. 규격 번호 → raw 폴더 대응표. 같은 번호의 폴더가 여럿이면(Release가 다른 경우) 버전이 가장 높은 것을 목적지로 쓴다.
- 같은 규격 안에 같은 표 번호가 두 번 나오면(원문 오류) 그 번호는 `ambiguous` 목적지로 표시하고 링크하지 않는다.

**2단계 — 참조 해석.** 본문에서 다음을 찾는다.
- `Table X-Y`, `Tables X-Y and X-Z`, `Table X-Y and X-Z`(뒤 번호에 "Table"이 생략된 나열), `Tables X-Y to X-Z`는 양끝만 링크.
- `clause/subclause/section N.N…`, `clauses N and M`.
- 다른 규격 지시: `of TS 38.214`, `in TS 38.214 [6]`, `TS 38.214 [6], clause …`, `[6]`, `[6, TS 38.214]`. 이 지시가 붙은 표·조항 참조는 그 규격으로 해석한다. 지시가 없으면 같은 규격.
- 대상 규격이 컬렉션에 없으면(예: TS 22.101) `missing_spec`. 규격은 있는데 번호가 없으면 `missing_target`. 둘 다 링크하지 않는다.
- 링크하지 않는 곳: front matter, 코드 펜스, 인라인/블록 수식(`$…$`, `$$…$$`), HTML 속성 값, 목적지 자신의 제목 줄(표 제목 줄의 `Table X-Y`). HTML `<table>` 안에서는 `<a href>`를 쓰고, 그 밖에서는 Markdown 링크를 쓴다.

**3단계 — 출력.**
```
linked/
├── index.json                       # 규격별 목적지 색인 (웹페이지 생성기용)
└── {spec}/
    ├── manifest.json                # raw manifest 사본 + link 통계
    ├── refs.json                    # 이 규격에서 나가는 모든 참조
    ├── clauses/*.md                 # 링크·앵커·역참조가 들어간 사본 (파일 이름은 raw와 같음)
    └── media → raw의 media를 가리키는 상대 경로 유지
```
- 앵커: 목적지 앞에 명시적 앵커를 넣는다. `<a id="table-8.1-2"></a>`, `<a id="figure-5.3.5-1"></a>`, 파일 안 하위 조항 제목 앞 `<a id="clause-5.2.2.2.1"></a>`. 파일 첫 조항은 파일 자체가 목적지다.
- 링크 형식: 같은 규격 `[Table 8.1-2](0123_8.1_xxx.md#table-8.1-2)`, 다른 규격 `[Table 5.1.2.1-2](../../38214-j50/clauses/....md#table-5.1.2.1-2)`. 원문 텍스트는 그대로 두고 링크로 감싸기만 한다.
- 역참조: 각 사본 파일 끝에 `## Referenced by` 절을 붙인다. 이 파일의 조항·표·그림을 가리키는 참조를 출처 규격·조항 순으로 나열한다. 규격 간 역참조를 포함한다.
- `refs.json` 항목: `{from_file, from_clause, line, text, kind: table|figure|clause, target_spec, target_id, target_file, anchor, status: resolved|ambiguous|missing_spec|missing_target}`. 정렬 순서 고정.
- media 경로: 사본의 이미지 링크를 raw media를 가리키는 상대 경로(`../../../raw/{spec}/media/...`)로 고쳐 쓴다. 심볼릭 링크는 쓰지 않는다. `check_links.py`의 "링크를 지우면 raw와 같다" 비교에서는 이 경로 치환도 되돌려서 비교한다.

**검사**: `skills/spec-linking/scripts/check_links.py linked/`
- 사본의 모든 링크가 존재하는 파일 + 존재하는 앵커로 가는가(ERROR).
- 사본에서 링크를 지우면 raw와 바이트 단위로 같은가(앵커·역참조 절 제외) — 링크 작업이 원문을 훼손하지 않았는지(ERROR).
- 규격별 status 분포, `missing_target` 상위 목록(WARN, 해석 규칙 개선 단서).
- 오케스트레이터 3단계(일괄 변환·검사) 뒤에 "링크" 단계를 추가해 자동으로 실행한다.

### 5.3 LLM 위키 (스킬 `llm-wiki`, 에이전트 `wiki-editor`)

Karpathy의 세 층에 맞춘다.

| 층 | 이 프로젝트 | 쓰기 권한 |
| --- | --- | --- |
| Raw sources | `raw/` (원문) + `linked/` (링크 사본). 인용은 `linked/`로 건다 | 읽기만 |
| Wiki | `wiki/` | LLM이 씀 |
| Schema | `wiki/SCHEMA.md` (플러그인 템플릿에서 처음 복사, 이후 사용자·LLM이 함께 고침) | 합의해서 고침 |

**위키 구조**
```
wiki/
├── SCHEMA.md       # 페이지 종류·형식·작업 절차. 모든 작업 전에 읽는다
├── index.md        # 모든 페이지: 링크 + 한 줄 요약 + (규격, 출처 수), 종류별 분류
├── log.md          # 추가만: "## [2026-11-26] ingest | 38.321 beam-failure-recovery"
├── features/       # 여러 규격에 걸친 기능 페이지 (beam-failure-recovery.md)
├── concepts/       # IE·타이머·채널·용어 (t310.md, pdcch.md)
├── specs/          # 규격별 요약: 범위, 장 구성, 주요 주제 (38.321.md)
└── answers/        # query 결과를 위키로 남긴 페이지
```
- 페이지 front matter: `type`, `title`, `sources`(인용한 linked 조항 경로 목록), `specs`(규격 + version 목록), `related`, `updated`. 값은 한 줄 스칼라나 JSON 배열(기존 규약과 같은 이유: PyYAML 없이 읽기).
- 모든 서술 문장은 하나 이상의 출처 링크(`../../linked/{spec}/clauses/...md#anchor`)를 단다. 원문 표·수식은 위키에 복사하지 않고 링크한다(원문 충실성은 linked가 맡는다).
- 서로 다른 규격·조항이 충돌해 보이면 지우지 않고 페이지에 `> CONFLICT:` 블록으로 남긴다.

**ingest** (단위 = 한 규격의 주제 하나, `raw/{spec}/topics/{id}.md`)
1. 대상 규격에 `topics.json`이 없으면 먼저 topic-grouping을 실행한다(기존 4단계).
2. 주제 파일을 읽고, 그 조항들의 `refs.json`에서 나가는 참조·들어오는 참조를 따라 다른 규격의 관련 조항을 확인한다(이것이 "관련 내용을 다 찾는" 근거).
3. 사용자에게 핵심 내용을 짧게 보고하고 방향을 받는다(대화형, 기본). 사용자가 "일괄로"라고 하면 묻지 않는다.
4. 관련 feature/concept/spec 페이지를 만들거나 고치고, index.md와 log.md를 갱신한다.
- **일괄 ingest**: 주제 여러 개를 Workflow로 나눠 읽을 때는 **읽기는 병렬, 쓰기는 하나**로 한다. 병렬 에이전트는 주제마다 "어느 페이지에 무엇을 넣을지" 제안을 `_workspace/wiki/{spec}_{topic}.json`에 쓰고, `wiki-editor` 하나가 차례로 반영한다. 같은 feature 페이지를 여러 에이전트가 동시에 고쳐 서로 덮어쓰는 것을 막기 위해서다.

**query**
1. `SCHEMA.md` → `index.md` → 관련 feature/concept 페이지 → 그 페이지의 출처 linked 조항으로 내려간다.
2. 위키에 없거나 얇으면 `linked/`를 grep하고 `refs.json` 역참조로 넓힌다. 예: 질문이 표 하나에 닿으면 그 표를 참조하는 모든 조항을 모은다.
3. 답은 출처 링크와 함께 사용자 언어로 준다. 위키가 다루지 못한 부분은 "위키에 없음, linked에서 직접 찾음"이라고 구분해 말한다.
4. 쓸 만한 답은 사용자에게 물어 `answers/`에 남기고 index·log를 갱신한다.

**lint**
- 스크립트(`lint_wiki.py`, 결정적): 깨진 링크, 출처 없는 페이지, index에 없는 페이지, 들어오는 링크가 없는 고아 페이지, 출처 앵커가 사라진 링크(재변환 후), front matter 형식.
- LLM 점검: 페이지 간 모순, 언급되지만 페이지가 없는 개념, 빠진 교차 링크, 더 ingest할 만한 주제 제안.

**에이전트 `wiki-editor`**: llm-wiki 스킬을 따라 위키 페이지를 쓰고 고친다. 일괄 ingest에서 유일한 쓰기 담당. 기존 topic-curator와 같은 형식(역할, 작업 원칙)으로 정의한다.

### 5.4 오케스트레이터 변경

`spec2md-orchestrator`에 단계를 추가한다: 3단계(일괄 변환·검사) → **3.5단계 링크**(`spec2md link` + `check_links.py`) → 4단계 주제 묶음. 위키(ingest/query/lint)는 질문이 잦고 독립적이므로 `llm-wiki` 스킬을 별도 진입점으로 두고, 오케스트레이터는 "위키 만들어줘" 요청을 llm-wiki로 넘긴다.

## 6. 사용자가 정한 것
- 플러그인 하나에 기존 하네스와 위키 스킬을 함께 담는다.
- 링크는 안 B(그래프 + 사본).
- Release 간 변화 추적은 나중에 결정.
- 링크 뷰어는 VS Code·브라우저(표준 Markdown 링크 + HTML 앵커).
- 위키 페이지는 영어, query 답은 한국어.
- 도구 구현에 더해 실데이터 검증(전체 link, 3개 규격 주제 묶음, BFR ingest·query)까지 이번 범위.

## 7. 설계자가 정한 것 (사용자 검토 대상)
- 플러그인을 `plugin/` 하위 폴더에 두고 데이터는 저장소 루트에 그대로 둔다. 개발은 `--plugin-dir ./plugin`으로 작업 사본을 직접 불러 쓴다.
- 링크 대상에 그림(Figure)도 포함.
- 사본 파일 끝에 `## Referenced by` 역참조 절.
- 같은 규격 번호가 여러 버전이면 가장 높은 버전으로 링크.
- 위키 폴더 이름·구조(`features/`, `concepts/`, `specs/`, `answers/`), 스키마 파일 이름 `wiki/SCHEMA.md`.
- ingest 단위 = 주제 파일 하나, 기본 대화형.
- 일괄 ingest는 읽기 병렬, 쓰기 단일.

## 8. 구현자에게 맡기는 것
- 참조 정규식 세부와 테스트 케이스 구성(위 패턴 목록은 최소 범위).
- `--only`로 일부 규격만 다시 만들 때 다른 규격 사본의 `Referenced by` 절을 어떻게 갱신할지.
- `check_links.py`, `lint_wiki.py`의 출력 형식(기존 `check_output.py`와 비슷하게).
- 플러그인 루트 경로를 스킬에서 참조하는 구체 방법(문서 확인 후).
