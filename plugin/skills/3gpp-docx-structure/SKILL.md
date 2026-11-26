---
name: 3gpp-docx-structure
description: "3GPP 규격(TS/TR) .docx 원본의 구조를 조사한다. 스타일 사용 빈도, 제목 개요(outline), 표·병합 셀·그림·수식·ASN.1 표지·변경 추적 개수를 scripts/inspect_docx.py로 뽑고, 3GPP 고유 스타일(B1, PL, TH, TF, NO, EX 등)의 의미를 해석한다. 새 규격 파일의 형식 분석, 변환 규칙을 정하기 전 사전 조사, '이 규격 docx 구조 봐줘', 변환 결과가 이상할 때 원본 확인에 사용한다. 변환 도구 구현은 spec-md-conversion, 변환 결과 검사는 conversion-check 스킬을 쓴다."
---

# 3GPP docx 구조 조사

변환 규칙은 실제 파일에서 확인한 사실을 바탕으로 정한다. 아래 스타일 표는 일반적인 3GPP 템플릿 기준이다. Release와 작업 그룹(WG)에 따라 스타일 이름이나 사용 방식이 달라질 수 있으므로 항상 스크립트로 다시 확인한다.

## 조사 절차

1. 구조 요약을 뽑는다. 표준 라이브러리만 쓰므로 설치할 것이 없다.
   ```
   uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_SKILL_DIR}/scripts/inspect_docx.py" 3gpp-specs/38331-i10.docx --samples 3
   uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_SKILL_DIR}/scripts/inspect_docx.py" 3gpp-specs/38331-i10.docx --json _workspace/01_inspect_38331-i10.json
   ```
   JSON 보고서는 `conversion-check` 스킬의 검사 스크립트가 입력으로 쓴다. 반드시 남긴다.
2. 스타일 빈도표에서 아래 표에 없는 스타일을 찾는다. 빈도가 높은 미지 스타일은 `--samples`로 예시 텍스트를 보고 역할을 판단한다.
3. 제목 개요를 확인한다. 번호 없는 제목, 부속서(Annex) 제목, `Void` 조항, 레벨이 건너뛰는 부분(1 다음에 바로 3)을 찾는다.
4. 표 개수와 병합 셀이 있는 표의 비율, 그림 종류(`media_files` 확장자: emf/wmf/png), 수식 수, ASN1START/STOP 짝이 맞는지 확인한다.
5. 필요하면 `word/document.xml`의 특정 부분을 직접 읽는다. 큰 파일이므로 통째로 출력하지 말고 Python으로 필요한 요소만 골라 본다.

## 3GPP 주요 스타일

| 스타일 | 의미 | 변환 시 주의 |
| --- | --- | --- |
| `heading 1`~`heading 6` | 조항 제목. 텍스트에 `5.3.5<TAB>제목` 형식으로 번호 포함 | 번호는 텍스트에서 파싱한다 |
| `heading 8` (TS) / `heading 9` (TR) | 부속서 제목 `Annex A (normative):<TAB>Title` | 레벨 1로 취급한다 |
| `H6` | 번호 없는 소제목 | 상위 파일 안의 하위 제목으로 둔다 |
| `B1`~`B5` | 들여쓰기 목록(레벨 1~5). 표지(`-`, `1>`, `a)`)가 텍스트에 직접 들어 있다 | 표지를 그대로 유지한다 |
| `PL` | 프로그램 목록(ASN.1, 코드) | 연속 문단을 하나의 코드 블록으로 묶는다 |
| `TH` / `TF` | 표 제목 / 그림 제목 | 캡션 |
| `TAH`, `TAC`, `TAL`, `TAR`, `TAN` | 표 셀: 머리글, 가운데, 왼쪽, 오른쪽, 표 안 NOTE | 표 셀 내용으로 처리한다 |
| `NO` | NOTE | 인용 블록 |
| `EX`, `EW` | 정의·약어 목록(용어<TAB>설명) | |
| `EQ` | 수식 문단(탭 정렬) | OMML이 있으면 수식으로 처리한다 |
| `TT`, `ZA`, `ZB`, `ZT`, `ZU`, `ZV`, `ZH` 등 `Z*` | 표지와 머리글 | 건너뛴다 |
| `TOC 1`~`TOC 9` | 목차 | 건너뛴다 |
| `CR*`, `Editor's Note` 계열 | 변경 요청서나 편집자 메모 | 발견하면 빈도를 보고하고 처리 방법을 정한다 |

## 보고서 형식

형식 분석 결과는 `_workspace/01_analyst_{spec}_format.md`에 쓴다. 다음 내용을 포함한다.

1. 파일 기본 정보(규격 번호, 버전, 크기, 제목 수, 최대 제목 레벨)
2. 스타일 빈도표와 각 스타일의 해석(위 표와 다른 점 강조)
3. 변환 시 위험 요소. 예: 병합 표 비율, EMF 그림 수, 수식 수, 번호 없는 제목, 비표준 스타일
4. 권장 `--split-depth`와 근거(레벨별 제목 수와 예상 파일 크기)
5. 출력 규약(`spec-md-conversion/references/output-contract.md`)을 바꾸거나 보완해야 할 점

추측과 확인한 사실을 구분해 적는다. 예: "`PL` 4,210개 확인", "`EW`는 약어 목록으로 보임(예시 3건 기준)".
