# spec2md

로컬 3GPP 규격(TS/TR) `.docx`를 조항(clause) 단위 Markdown raw 파일(영어)로 충실하게 변환하고, 참조 링크를 붙인 사본과 LLM 위키까지 만드는 도구다. Python 변환 도구와 이를 조율하는 Claude Code 플러그인(스킬·에이전트)으로 구성된다.

## 흐름

```
3gpp-specs/*.docx  ──convert/batch──▶  raw/{spec}/      조항별 md, manifest.json, media/, topics/
                                     │
                                  ──link──▶  linked/{spec}/   참조 링크·<a id> 앵커·"Referenced by" 절
                                                 │
                                              ──llm-wiki──▶  wiki/   주제·기능·개념 페이지
```

- `raw/`는 원문에 충실한 변환본이고, `linked/`는 그 사본에 링크를 더한 것이다. 둘 다 생성물이라 직접 고치지 않고 다시 만든다.
- 위키는 `linked/`만 인용한다.
- `3gpp-specs/`, `raw/`, `linked/`, `wiki/`는 git에 올리지 않는다.

## 설치

이 저장소 자체가 Claude Code 마켓플레이스(`spec2md`)다. 변환만 쓸 사람은 clone할 필요가 없고, 도구를 고칠 사람만 clone한다.

### 사용자: clone 없이 GitHub에서 설치

```
claude plugin marketplace add CW-Nam/spec2md
claude plugin install spec2md@spec2md
```

Claude Code 안에서는 `/plugin marketplace add CW-Nam/spec2md`, `/plugin install spec2md@spec2md`로 해도 된다. `--scope project`를 붙이면 현재 프로젝트의 `.claude/settings.json`에만 켜진다.

팀이 쓰는 프로젝트에서는 `.claude/settings.json`에 아래를 넣어 두면, 그 폴더에서 Claude Code를 연 사람에게 마켓플레이스 추가와 설치를 안내한다.

```json
{
  "extraKnownMarketplaces": {
    "spec2md": {
      "source": { "source": "github", "repo": "CW-Nam/spec2md" }
    }
  },
  "enabledPlugins": {
    "spec2md@spec2md": true
  }
}
```

**[uv](https://docs.astral.sh/uv/)가 필요하다.** 스킬은 `uv run --project "${CLAUDE_PLUGIN_ROOT}" ...`로 스크립트를 실행하고, uv가 플러그인의 `pyproject.toml`·`uv.lock`에 맞춰 Python(3.11 이상)과 의존성(`lxml`, `olefile` 등)을 플러그인 폴더의 `.venv`에 처음 한 번 설치한다. 따로 `pip install`할 필요는 없다. uv가 없으면 세션 시작 훅이 설치 방법을 알려 준다.

```
winget install --id=astral-sh.uv -e                  # Windows
curl -LsSf https://astral.sh/uv/install.sh | sh      # macOS/Linux
```

uv를 쓸 수 없으면 `pip install -r <플러그인 폴더>/requirements.txt` 후 `python <플러그인 폴더>/scripts/spec2md.py ...`로 직접 실행할 수 있다(스킬 명령은 uv 기준이다).

**업데이트:** `claude plugin marketplace update spec2md` 후 `/plugin`에서 업데이트한다. 원격 설치본은 `~/.claude/plugins/cache/` 아래 복사본이라, 저장소에서 `plugin/.claude-plugin/plugin.json`의 `version`을 올려야 새 내용이 내려간다.

변환·링크·위키 작업 폴더(`3gpp-specs/`, `raw/`, `linked/`, `wiki/`)는 Claude Code를 연 현재 폴더 기준이다.

### 개발자: clone해서 로컬 마켓플레이스로 설치

```
git clone https://github.com/CW-Nam/spec2md.git
cd spec2md
uv sync --project plugin       # plugin/.venv에 의존성 설치 (dev 그룹 포함)
claude plugin marketplace add ./
claude plugin install spec2md@spec2md --scope project
```

로컬 마켓플레이스 플러그인은 제자리에서 로드되므로 `plugin/`을 고친 뒤 `/reload-plugins`만 하면 반영된다. 변환 도구를 고치는 `converter-developer` 에이전트는 `${CLAUDE_PLUGIN_ROOT}/src/`를 직접 수정하므로 이 방식에서만 쓴다. 원격 설치본에서 고치면 캐시에만 남았다가 업데이트 때 사라진다.

같은 이름의 마켓플레이스가 이미 GitHub 출처로 등록돼 있으면 먼저 `claude plugin marketplace remove spec2md`로 지운다.

## 사용법

### Claude Code에서

자연어로 요청하면 `spec2md-orchestrator` 스킬이 형식 분석 → 도구 수정 → 일괄 변환 → 검사 → 주제 묶음을 조율한다.

- "3gpp-specs/ 규격 전부 md로 변환해줘", "38.331만 다시 변환해줘"
- "변환 결과 검사해줘", "주제별로 묶어줘"
- "링크 만들어줘", "○○ 주제 위키에 넣어줘", "위키 점검"

### CLI 직접 실행

```
uv run --project plugin spec2md batch 3gpp-specs/ -o raw/                 # 일괄 변환
uv run --project plugin spec2md batch 3gpp-specs/ -o raw/ --only 38331-j40 --depth 38331-j40=4
uv run --project plugin spec2md convert 3gpp-specs/24007-j50.docx -o raw/  # 한 규격
uv run --project plugin spec2md link raw -o linked                   # 참조 링크 사본
uv run --project plugin spec2md topics raw/38213-j50/                # topics/topics.json → 주제 파일
```

`--project`는 작업 폴더를 바꾸지 않으므로 상대 경로는 현재 폴더 기준이다. 검사 스크립트는 `uv run --project plugin python plugin/skills/.../scripts/X.py ...`로 실행한다.

- `--split-depth N`(기본 3): 조항 파일로 나눌 제목 깊이. `--max-chars`(기본 60000): 파일 하나의 최대 크기.
- 분할 배포된 규격(`36101-j60_cover.docx`, `36101-j60_s00-07.docx` …)은 `batch`가 같은 코드끼리 묶어 `raw/36101-j60/` 하나로 만든다. `convert`로 할 때는 파트 파일을 모두 넘긴다.

### 출력 검사

| 스크립트 | 검사 대상 |
| --- | --- |
| `plugin/skills/conversion-check/scripts/check_output.py` | 한 규격의 raw 출력 (제목 누락, manifest 불일치, 깨진 이미지 링크, 코드 펜스 등) |
| `plugin/skills/spec2md-orchestrator/scripts/check_all.py` | `3gpp-specs/` 전체에 대한 raw 출력 |
| `plugin/skills/spec-linking/scripts/check_links.py` | `linked/`의 링크·앵커·원문 일치 |
| `plugin/skills/topic-grouping/scripts/check_topics.py` | `topics.json` |
| `plugin/skills/llm-wiki/scripts/lint_wiki.py` | `wiki/` |

출력 형식의 기준은 [`plugin/skills/spec-md-conversion/references/output-contract.md`](plugin/skills/spec-md-conversion/references/output-contract.md)다. 형식을 바꾸면 변환 도구와 검사 스크립트를 함께 고친다.

## 저장소 구조

```
.claude-plugin/marketplace.json   마켓플레이스 정의 (이름 spec2md)
plugin/
├── src/spec2md/                  변환 도구 (reader, headings, blocks, omml/mtef 수식, split, link*, topics, cli)
├── pyproject.toml, uv.lock       의존성 정의·고정 (uv). requirements.txt는 pip 대안용
├── scripts/spec2md.py            패키지 설치 없이 실행하는 진입점 (pip 대안)
├── hooks/                        SessionStart uv 설치 확인 훅 (check_deps.py)
├── tests/                        pytest
├── skills/                       스킬 7개 (오케스트레이터, docx 구조 분석, 변환, 검사, 링크, 주제 묶음, 위키)
└── agents/                       에이전트 5개 (형식 분석, 변환 개발, 검사, 주제 큐레이션, 위키 편집)
_workspace/                       에이전트 작업 파일 (01_analyst_*.md만 추적)
docs/                             설계·계획 문서
```

## 테스트

```
uv run --project plugin pytest -q plugin
```

의존성을 바꿀 때는 `plugin/`에서 `uv add 패키지==버전`(테스트 전용은 `uv add --dev`)을 쓰고 `uv.lock`을 함께 커밋한다. `requirements.txt`도 같은 버전으로 맞춘다. 원격 설치본에도 `uv.lock`이 함께 내려가므로 사용자 환경에도 같은 버전이 설치된다.

테스트는 `tests/docx_builder.py`로 작은 docx를 직접 만들어 변환 결과를 확인한다. `python-docx`는 만든 docx가 올바른 문서인지 확인하는 데만 쓴다.
