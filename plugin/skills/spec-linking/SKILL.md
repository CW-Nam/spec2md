---
name: spec-linking
description: "변환된 3GPP raw Markdown(raw/{spec}/)에서 표·그림·조항 참조를 찾아 규격 안팎으로 링크하고, 앵커와 역참조('Referenced by') 절이 들어간 사본을 linked/에 만든다. 만든 뒤 독립 검사기로 링크·앵커·원문 일치를 확인한다. '링크 만들어줘', '참조 링크', 'linked 다시', '재변환 후 링크 갱신', '해석 실패 개선', 'missing_target 줄여줘'에 사용한다. 조항 변환 자체는 spec-md-conversion 스킬이 다룬다."
---

# 참조 링크 만들기와 검사

`raw/`는 원문에 충실한 변환 결과이며 이 스킬은 `raw/`를 고치지 않는다. 링크는 별도 폴더 `linked/`에 만든다. 위키 단계(`spec2md:llm-wiki`)는 `linked/`를 입력으로 쓴다.

## 실행

```
uv run --project "${CLAUDE_PLUGIN_ROOT}" spec2md link raw -o linked
uv run --project "${CLAUDE_PLUGIN_ROOT}" spec2md link raw -o linked --only 38213-j50   # 일부만
```

- 같은 입력이면 결과가 같다(결정적). `linked/{spec}/`는 실행할 때마다 지우고 새로 쓴다.
- `--only`는 선택한 규격만 다시 쓴다. 선택하지 않은 규격의 "Referenced by" 절은 갱신되지 않으므로, 재변환 뒤에는 전체를 다시 실행하는 것이 기본이다.
- 출력 형식(앵커 줄, 링크 형식, `refs.json`, `index.json`, 역참조 절, 줄바꿈 규칙)은 [출력 규약 7절](../spec-md-conversion/references/output-contract.md)을 따른다.

## 검사

```
uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_SKILL_DIR}/scripts/check_links.py" linked --raw raw --json _workspace/05_link_check.json
```

`check_links.py`는 링크 도구와 코드를 공유하지 않는 독립 검사기다(표준 라이브러리만 사용). 종료 코드 0이어야 한다.

| 구분 | 내용 |
| --- | --- |
| ERROR | `.md` 링크와 `<a href>`의 파일이 없음(`broken link`), `#anchor`가 대상 파일에 `<a id>`로 없음(`broken anchor`) |
| ERROR | 링크 텍스트의 번호와 앵커가 의미상 다름(`anchor mismatch`: `Table N`은 `table-N`, `Figure N`은 `figure-N`, 조항은 `clause-N`), `<table>` 안에 Markdown 링크가 남음(`markdown link inside <table>`) |
| ERROR | 사본에서 앵커 줄·생성된 링크·역참조 절·media 접두사를 되돌린 결과가 raw와 바이트 단위로 다름(`differs from raw`) |
| ERROR | raw의 본문 파일이 linked에 없음(`missing`) |
| WARN | 규격별 status 분포(`resolved`, `missing_target`, `missing_spec`, `ambiguous`), `missing_target` 상위 20개 `(target_spec, kind, target_id, 개수)` |

ERROR가 있으면 링크 도구 결함이다. 원인을 진단해 `converter-developer`에 넘기고, 검사 기준을 느슨하게 바꿔 통과시키지 않는다.

## 해석 규칙 개선 절차

WARN은 실패가 아니라 해석하지 못한 참조의 목록이다. 줄이려면 다음 순서로 한다.

1. 검사 결과의 `missing_target` 상위 항목과 `refs.json`의 해당 행(`from_file`, `line`, `text`)을 연다.
2. 원문(`raw/`의 해당 파일과 대상 규격)에서 그 번호를 직접 확인한다. 둘 중 하나로 구분한다.
   - **진짜 없는 번호**: 원문의 오타이거나 다른 Release에만 있는 조항이다. 그대로 둔다.
   - **해석 패턴 누락**: 번호는 있는데 도구가 찾지 못했다(예: 새로운 나열 형태, 제목 번호 모양, 규격 지시 형태).
3. 패턴 누락이면 `${CLAUDE_PLUGIN_ROOT}/tests/test_link_refs.py`에 **실제 문장**으로 실패하는 테스트를 먼저 추가한다. 그 다음 `link_refs.py`나 `link_index.py`를 고쳐 통과시킨다.
4. 전체 테스트(`uv run --project "${CLAUDE_PLUGIN_ROOT}" pytest -q "${CLAUDE_PLUGIN_ROOT}/tests"`)와 `link` → `check_links.py`를 다시 실행해 ERROR가 0이고 WARN이 줄었는지 확인한다.

## 금지

- `raw/` 파일을 고치지 않는다. 링크 때문에 원문이 바뀌면 검사기가 ERROR로 잡는다.
- 추측 링크를 만들지 않는다. 대상이 없거나 모호하면(`missing_target`, `missing_spec`, `ambiguous`) 링크하지 않고 텍스트를 그대로 둔다.
- 이 스킬에서 `linked/`를 저장소 안 `raw/` 아래에 만들지 않는다(출력은 `raw`와 분리된 폴더).
