---
name: llm-wiki
description: "링크된 3GPP 규격 사본(linked/)을 근거로 영어 LLM 위키(wiki/)를 만들고 유지한다. 주제를 위키에 넣고(ingest), 위키와 linked/를 근거로 질문에 답하고(query), 위키를 점검한다(lint). '위키 만들어줘', '위키에 넣어줘', '○○ 주제 ingest', '○○ 기능 관련 내용 다 알려줘', '위키 점검', '위키 lint', 위키 기반 질문에 사용한다. docx 변환은 spec-md-conversion, 참조 링크 만들기는 spec-linking, 주제 묶기는 topic-grouping 스킬이 다룬다."
---

# LLM 위키 만들기와 유지

위키는 세 층으로 나뉜다. `raw/`·`linked/`는 원문 층이라 읽기만 한다. `wiki/`는 LLM이 쓴다. `wiki/SCHEMA.md`는 위키 규칙이며 사용자와 합의해서만 고친다. 페이지 형식·링크 형식·index·log 형식은 모두 `wiki/SCHEMA.md`가 정한다. 이 스킬은 절차만 정한다.

작업 폴더에는 `raw/`, `linked/`, `wiki/`, `_workspace/`가 나란히 있다. 위키 페이지는 영어로 쓰고, query 답은 사용자 언어로 준다.

## 시작할 때 (모든 작업 공통)

1. `linked/`가 없으면 멈추고 사용자에게 `spec2md:spec-linking` 스킬로 링크를 먼저 만들라고 안내한다. 위키 출처는 `linked/`에만 건다.
2. `wiki/SCHEMA.md`가 없으면 위키를 새로 만든다.
   - `${CLAUDE_SKILL_DIR}/templates/SCHEMA.md`를 `wiki/SCHEMA.md`로 복사한다.
   - `wiki/index.md`를 `# Wiki Index` 제목과 빈 `## Features`, `## Concepts`, `## Specs`, `## Answers` 절로 만든다.
   - `wiki/log.md`를 `# Wiki Log` 제목만으로 만든다.
3. `wiki/SCHEMA.md`를 항상 먼저 읽는다. 사용자가 고친 규칙이 템플릿보다 우선한다.

## ingest — 주제 하나를 위키에 넣기

단위는 한 규격의 주제 하나(`raw/{spec}/topics/{id}.md`)다.

1. **주제 확인.** `raw/{spec}/topics/topics.json`이 없으면 `spec2md:topic-grouping` 스킬로 주제를 묶고 `uv run --project "${CLAUDE_PLUGIN_ROOT}" spec2md topics raw/{spec}/`로 주제 파일을 만든다.
2. **주제와 관련 내용 읽기.**
   - 주제 파일을 읽는다. 조항마다 앞에 있는 `<!-- source: clauses/{file}.md -->` 주석이 출처다. 인용할 사본은 `linked/{spec}/clauses/{file}.md`다.
   - **나가는 참조:** `linked/{spec}/refs.json`에서 `from_file`이 주제 조항(`clauses/{file}.md`)이고 `status`가 `resolved`인 행을 모은다. `target_spec`·`target_file`·`anchor`가 가리키는 조항, 특히 다른 규격의 조항을 확인한다(경로는 `linked/{target 규격 코드}/{target_file}`, 규격 코드는 `linked/index.json`에서 번호로 찾는다).
   - **들어오는 참조:** 주제 조항 사본 끝의 `## Referenced by` 절에 나열된 조항을 확인한다. 다른 규격에서 이 주제를 쓰는 곳(예: TS 38.331의 설정 IE)이 여기서 나온다.
   - 한 단계만 따라간다. 따라간 조항의 참조를 다시 따라가지 않는다. 맥락이 넘치면 주제와 관계가 먼 조항부터 뺀다.
   - 이미 있는 위키 페이지(`index.md`에서 찾음) 중 이 내용이 들어갈 페이지를 확인한다.
3. **방향 확인(대화형, 기본).** 사용자에게 핵심을 3–5줄로 보고한다: 주제 범위, 관련된 다른 규격 조항, 만들거나 고칠 페이지 목록(feature/concept/spec), 충돌로 보이는 곳. 그 다음 방향을 묻고 답을 기다린다. 사용자가 "일괄로"라고 했으면 묻지 않고 4로 간다.
4. **쓰기.** `wiki/SCHEMA.md`에 따라 feature·concept·spec 페이지를 만들거나 고친다. 기존 페이지는 덮어쓰지 않고 내용을 합친다(출처는 `sources`에 합집합). `index.md`에 페이지 줄을 넣거나 고치고, `log.md`에 `## [YYYY-MM-DD] ingest | 38.321 beam-failure-recovery` 형식 항목을 덧붙인다. 마지막으로 lint 스크립트를 실행한다(아래 "매 작업 끝").

## 일괄 ingest — 주제 여러 개

읽기는 병렬, 쓰기는 하나로 한다. 같은 feature 페이지를 여러 에이전트가 동시에 고쳐 서로 덮어쓰는 것을 막기 위해서다. 일괄 ingest는 방향을 묻지 않는다(위 3단계 생략).

1. **제안(병렬).** 주제마다 Agent를 하나씩 띄운다. 한 번에 최대 5개까지 한 메시지에서 병렬로 호출하고, 주제가 더 많으면 앞의 묶음이 끝난 뒤 다음 5개를 띄운다.
   - `subagent_type: "spec2md:wiki-editor"`
   - `prompt`: "제안 모드. raw/{spec}/topics/{id}.md를 llm-wiki 스킬의 ingest 1–2단계대로 읽고, wiki/SCHEMA.md에 맞는 페이지 제안을 _workspace/wiki/{spec}_{id}.json에만 써라. wiki/ 파일은 고치지 마라."
2. **제안 파일 형식** `_workspace/wiki/{spec}_{topic}.json` (`{spec}`은 규격 코드, 예: `38321-j40`):

   ```json
   {
     "spec": "38321-j40",
     "topic": "beam-failure-recovery",
     "pages": [
       {"path": "features/beam-failure-recovery.md", "action": "create", "type": "feature",
        "title": "Beam Failure Recovery",
        "content_md": "# Beam Failure Recovery (page body in Markdown) ...",
        "sources": ["linked/38321-j40/clauses/0075_5.17_beam-failure-detection-and-recovery-procedure.md"]}
     ],
     "log": "38.321 beam-failure-recovery"
   }
   ```

   - `path`: `wiki/` 기준 경로. `action`: `create`(새 페이지) 또는 `update`(기존 페이지에 합칠 내용).
   - `content_md`: front matter를 뺀 본문. `create`면 페이지 본문 전체, `update`면 기존 페이지에 합칠 절·문단. 링크는 그 페이지(`path`) 위치에서 본 상대 경로로 쓴다(`../../linked/...`).
   - `sources`: 본문이 인용한 `linked/` 경로(작업 폴더 기준). 비어 있으면 안 된다.
   - `log`: 반영할 때 `## [YYYY-MM-DD] ingest | {log}`가 될 텍스트.
3. **반영(하나).** 모든 제안 에이전트가 끝나면 `spec2md:wiki-editor`를 하나만 띄운다.
   - `prompt`: "반영 모드. _workspace/wiki/의 제안 파일(목록: …)을 파일 이름 순서대로 wiki/에 반영하라. 페이지별로 합치고, front matter·index.md·log.md를 갱신하고, 끝나면 lint를 실행해 ERROR를 0으로 만들어라. 반영한 파일은 _workspace/wiki/applied/로 옮겨라."
   - 반영 에이전트는 front matter를 만든다: `type`·`title`은 제안에서, `sources`는 기존 값과 제안의 합집합, `specs`는 출처 조항 파일 front matter의 `spec`·`version`(`"TS 38.321 19.4.0"`), `updated`는 오늘 날짜.
4. 반영 에이전트의 보고(만들고 고친 페이지 수, lint 결과, 남은 CONFLICT)를 사용자에게 전한다.

## query — 위키로 답하기

1. `wiki/SCHEMA.md` → `wiki/index.md` → 관련 feature·concept 페이지 → 그 페이지의 출처 `linked/` 조항 순서로 내려간다.
2. 위키에 없거나 얇으면 `linked/`를 grep하고, `refs.json`과 `## Referenced by` 절로 넓힌다. 예: 질문이 표 하나에 닿으면 `refs.json`에서 그 표(`kind: table`, `target_id`)를 가리키는 모든 조항을 모은다.
3. 답은 사용자 언어로, 출처 링크와 함께 준다. 위키에서 온 내용과 "위키에 없음, linked에서 직접 찾음" 내용을 구분해 말한다. 출처가 없는 내용은 답하지 않거나 추정이라고 밝힌다.
4. 남길 만한 답이면 사용자에게 `answers/`에 저장할지 묻는다. 저장하면 영어로 `answers/{kebab-case}.md`(type `answer`)를 쓰고, 관련 feature·concept 페이지에서 링크하고, `index.md`와 `log.md`(`query` 항목)를 갱신한 뒤 lint를 실행한다.

## lint — 위키 점검

```
uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_SKILL_DIR}/scripts/lint_wiki.py" wiki --json _workspace/06_wiki_lint.json
```

`lint_wiki.py`는 표준 라이브러리만 쓰는 결정적 검사기다. 종료 코드 0 = ERROR 없음, 1 = ERROR 있음, 2 = 입력 오류.

| 구분 | 내용 |
| --- | --- |
| ERROR | 상대 링크의 파일이 없음, `#anchor`가 대상 파일의 `<a id>`나 제목 slug에 없음(재변환 후 사라진 출처 포함) |
| ERROR | front matter `sources` 항목의 파일이 없거나 `#anchor`가 대상에 없음(본문 링크와 같은 규칙, 경로는 위키 상위 폴더 기준) |
| ERROR | front matter에 `type`·`title`·`sources`·`specs`·`updated` 중 빠진 키, `sources`가 비어 있거나 한 줄 JSON 배열이 아님, `type`이 `feature`·`concept`·`spec`·`answer`가 아님 |
| ERROR | `index.md`에 링크되지 않은 페이지, `index.md` 없음 |
| ERROR | `log.md`에서 `## [`로 시작하는 줄이 SCHEMA 8절 형식(`## [YYYY-MM-DD]`, 작업 이름 `ingest`·`query`·`lint` 중 하나, 세로 막대, 텍스트 순서)이 아님 |
| WARN | 고아 페이지(다른 페이지에서 들어오는 링크 없음. index·log·SCHEMA는 세지 않음) |
| WARN | `linked/` 링크가 없는 본문 문단이 5개 이상인 페이지 |

1. 스크립트를 실행하고 ERROR를 모두 고친다. 깨진 출처 링크는 새 `linked/`에서 같은 조항(번호·제목)을 찾아 고친다. 찾을 수 없으면 그 서술을 지우지 말고 사용자에게 보고한다.
2. WARN을 검토해 고칠 수 있는 것은 고친다(교차 링크 추가, 출처 달기).
3. 스크립트가 못 보는 것을 LLM이 점검해 보고한다: 페이지 사이의 모순(→ `> CONFLICT:` 블록 후보), 언급되지만 페이지가 없는 개념, 빠진 교차 링크, 더 ingest할 만한 주제.
4. `log.md`에 `## [YYYY-MM-DD] lint | N errors, M warnings` 항목을 덧붙인다.

## 매 작업 끝

`index.md`와 `log.md`를 갱신한 뒤 lint 스크립트를 실행하고 ERROR가 0인지 확인한다. ERROR가 남으면 고쳐서 다시 실행한다. 결과(페이지 수, ERROR·WARN 수)를 사용자에게 한 줄로 알린다.

## 금지

- `raw/`와 `linked/`를 고치지 않는다. 출처가 틀려 보이면 사용자에게 보고한다(원문 문제는 변환·링크 단계에서 고친다).
- 출처 없는 서술을 쓰지 않는다. 일반 지식으로 빈칸을 채우지 않는다.
- 원문 표·수식을 위키에 복사하지 않는다. 링크하고 무엇을 정의하는지 한 문장으로 쓴다.
- 충돌해 보이는 서술을 지우거나 한쪽만 고르지 않는다. `> CONFLICT:` 블록으로 남긴다.
- `wiki/SCHEMA.md`를 사용자와 합의 없이 고치지 않는다.
- 일괄 ingest에서 제안 에이전트가 `wiki/`를 직접 고치게 하지 않는다.
