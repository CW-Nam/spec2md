---
name: spec2md-orchestrator
description: 3GPP TS/TR DOCX를 영어 Markdown으로 변환·재변환하고 결과를 검사한다. spec2md 변환기 개발·수정, 특정 규격 재변환, 참조 링크 갱신, 조항의 주제별 묶음에 사용한다. 위키 작성·질의와 규격 내용에 관한 단순 질문은 별도로 다룬다.
---

# spec2md 오케스트레이터

저장소 루트에서 기존 `uv run --project plugin` 명령을 사용한다. 입력 DOCX는 읽기 전용으로 다룬다. 원문의 조항·표·그림·수식·코드를 충실하게 옮기고, 변환 검사는 원본과 결과 사이의 누락 및 형식 오류에 적용한다. [출력 규약](../../../plugin/skills/spec-md-conversion/references/output-contract.md)이 형식의 기준이다.

## 요청 범위 확인

- 변환·검사 전에 `3gpp-specs/`의 입력과 `raw/`의 기존 출력을 확인한다. 요청한 규격 번호를 실제 파일명과 대조해 릴리스가 포함된 코드(예: `38331-i10`)를 찾는다. 같은 코드의 분할 파일은 하나의 규격으로 처리한다. 대상 입력이 없으면 누락을 알리고 진행 가능한 작업을 이어간다.
- 변환·검사·링크·주제 묶음 중 요청에 필요한 단계만 실행한다. 검사만 요청받으면 기존 출력을 검사한다. 기존 변환기로 처리할 수 있는 입력은 곧바로 변환하고, 새 형식이나 변환 결함을 조사할 때 원본 구조를 분석한다.
- 기존 작업 보고서는 `_workspace/`에서 확인한다. 새로운 샘플 출력이나 보고서는 해당 작업을 구분할 수 있는 경로에 둔다.

## 분석과 변환기 수정

새 형식이나 변환 오류를 조사할 때 [DOCX 구조 분석 절차](../../../plugin/skills/3gpp-docx-structure/SKILL.md)를 참고한다. 다음은 `38331-i10` 예시다. `_workspace/`가 없으면 먼저 만들고, 분할 규격이면 모든 파트 경로를 함께 넘긴다.

```text
uv run --project plugin python plugin/skills/3gpp-docx-structure/scripts/inspect_docx.py 3gpp-specs/38331-i10.docx --json _workspace/01_inspect_38331-i10.json
```

변환기를 수정할 때는 [변환 규칙](../../../plugin/skills/spec-md-conversion/SKILL.md)과 출력 규약을 참고한다. 영향받는 샘플을 별도 출력 폴더에 변환하고, 아래 검사 명령의 `--raw`에 그 폴더를 지정해 원본과 대조한다. 원인을 수정한 뒤 `uv run --project plugin pytest -q plugin`과 영향받는 샘플 검사를 통과시키고, 공통 변환 로직을 바꿨다면 기존 통과 샘플도 확인한다. 형식 규약을 변경할 때는 관련 검사 기준을 함께 검토한다.

## 변환과 검사

전체 변환과 검사의 기본 명령은 다음과 같다.

```text
uv run --project plugin spec2md batch 3gpp-specs/ -o raw/
uv run --project plugin python plugin/skills/spec2md-orchestrator/scripts/check_all.py --specs 3gpp-specs --raw raw --ws _workspace --phase 03
```

- 일부 규격만 처리하려면 두 명령에 같은 `--only 38331-i10,38300-i00` 형태의 코드 목록을 붙인다. 출력 분할 깊이가 필요한 경우 `batch`의 `--split-depth` 또는 규격별 `--depth CODE=N`을 사용한다. 파일 경로를 직접 지정할 때는 `convert`에 같은 규격의 모든 파트를 넘긴다.
- 개별 입력을 직접 지정한 경우에는 그 입력의 구조 분석 JSON과 규격 출력 폴더를 `check_output.py`에 넘겨 확인할 수 있다.
- 변환 CLI의 실패 목록과 `_workspace/03_check_summary.json`을 함께 확인한다. 요청한 규격마다 새 변환 성공과 검사 `PASS`를 확인한다. 진단에는 요약이 가리키는 개별 보고서와 [변환 검사 절차](../../../plugin/skills/conversion-check/SKILL.md)를 활용한다. 실패한 출력은 후속 작업에서 완료본으로 취급하지 않는다.

## 참조 링크

링크 생성·갱신이 요청 범위에 있으면 검증된 `raw/`를 사용한다. 링크 CLI는 입력 코퍼스의 manifest를 모두 읽으므로, 실패한 변환의 잔여 출력이 있으면 먼저 해결하거나 검증된 입력을 별도 경로에 모아 처리한다. 재변환 뒤 링크를 갱신할 때는 규격 간 역참조도 갱신되도록 전체 코퍼스를 다시 링크한다. `linked/`는 CLI로 재생성한다.

```text
uv run --project plugin spec2md link raw -o linked
uv run --project plugin python plugin/skills/spec-linking/scripts/check_links.py linked --raw raw --json _workspace/05_link_check.json
uv run --project plugin python plugin/skills/spec-linking/scripts/mk_unresolved.py . _workspace/05_link_unresolved.html
```

링크 검사가 끝나면 마지막 명령으로 미해결 참조 점검용 HTML을 만든다(템플릿 `unresolved_tpl.html`이 스크립트와 같은 폴더에 있어야 한다). 링크 검사에서 `ERROR`가 나오면 생성 결과와 원문을 대조해 원인을 찾는다. 미해결 참조는 [링크 규칙](../../../plugin/skills/spec-linking/SKILL.md)에 따라 원문 근거와 함께 보고하고, 점검용 HTML 경로를 함께 알린다.

## 주제별 묶음

요청 시 변환 검사를 통과한 규격의 `manifest.json`과 필요한 조항을 읽고, [주제 분류 규칙](../../../plugin/skills/topic-grouping/SKILL.md)에 따라 `raw/{spec}/topics/topics.json`을 작성하거나 갱신한다. 기존 분류의 주제 ID는 유지한다. 아래 검사에 통과하면 주제 Markdown을 생성한다.

```text
uv run --project plugin python plugin/skills/topic-grouping/scripts/check_topics.py raw/38331-i10
uv run --project plugin spec2md topics raw/38331-i10
```

실행한 단계별로 처리한 규격 수, 검사 통과와 실패, 남은 경고, 산출물과 보고서 경로를 요약한다.
