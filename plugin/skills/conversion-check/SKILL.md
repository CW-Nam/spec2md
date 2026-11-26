---
name: conversion-check
description: "spec2md가 만든 Markdown raw 출력(raw/{spec}/)이 원본 docx에서 무엇을 잃었거나 깨뜨렸는지 검사한다. 제목 누락, manifest·파일 불일치, front matter 누락, 깨진 이미지 링크, 짝이 안 맞는 코드 펜스, XML 잔여물, ASN.1 표지 수, 표·그림 개수, 파일 크기 분포를 scripts/check_output.py로 확인하고 원인별 보고서를 쓴다. '변환 결과 검사', '누락 확인', '변환 품질 점검', 변환 도구를 고친 뒤 회귀 확인에 사용한다. 규격 내용이 기술적으로 맞는지 검증하는 용도가 아니다."
---

# 변환 결과 구조 검사

이 검사는 **구조 충실도**만 본다. 원문에 있던 조항, 표, 코드, 그림이 빠짐없이 옮겨졌는지, 출력이 출력 규약(`spec-md-conversion/references/output-contract.md`)을 지키는지를 확인한다. 규격 내용이 기술적으로 맞는지는 판단하지 않는다. 이 단계의 목표는 raw 파일 생성이기 때문이다.

## 절차

1. 원본 구조 보고서가 없으면 만든다.
   ```
   python "${CLAUDE_PLUGIN_ROOT}/skills/3gpp-docx-structure/scripts/inspect_docx.py" specs/{file}.docx --json _workspace/01_inspect_{spec}.json
   ```
2. 검사 스크립트를 실행한다.
   ```
   python "${CLAUDE_SKILL_DIR}/scripts/check_output.py" --inspect _workspace/01_inspect_{spec}.json --out raw/{spec} --json _workspace/{phase}_checker_{spec}.json
   ```
   종료 코드 0은 오류 없음(경고는 있을 수 있음), 1은 오류 있음, 2는 입력 파일 문제다.
3. 스크립트가 잡지 못하는 부분은 표본으로 직접 본다. 원본에서 표·ASN.1·그림·부속서가 많은 조항을 3~5개 고르고, 원본 텍스트(`inspect_docx.py --samples`나 XML 직접 조회)와 출력 파일을 나란히 비교한다. 다음을 확인한다.
   - 병합 셀이 있는 표의 행과 열이 어긋나지 않았는가
   - `1>`/`2>` 목록 표지와 들여쓰기가 남아 있는가
   - 표 제목과 그림 제목이 해당 표·그림 옆에 있는가
   - 문단이 합쳐지거나 중간에 잘리지 않았는가
4. 보고서를 `_workspace/{phase}_checker_report_{spec}.md`에 쓴다.

## 판정 기준

| 등급 | 의미 | 예 |
| --- | --- | --- |
| **ERROR** | 내용 손실이나 규약 위반. 수정해야 완료할 수 있다 | 제목 누락, 파일 없음, front matter 누락, 펜스 짝 불일치, XML 잔여물, ASN1START 수 불일치, 깨진 이미지 링크 |
| **WARNING** | 의도한 결과일 수 있다. 이유를 확인해 보고서에 적는다 | 표 개수 차이(표지 표를 건너뛴 경우), 너무 크거나 작은 파일, 고아 파일, BOM |
| **NOTE** | 표본 비교에서 발견했지만 규약에 정한 기준이 없는 품질 문제 | 표 안 줄바꿈이 어색함 |

경고를 오류처럼 막지 않는다. 다만 왜 정상인지 확인하지 않은 경고를 "문제 없음"으로 보고하지 않는다.

## 보고서 형식

```markdown
# 변환 검사: {spec} (tool {tool_version}, split_depth {n})
결과: PASS | FAIL  (ERROR {n} / WARNING {n} / NOTE {n})

## 원인별 문제
### 1. {원인 가설} — ERROR
- 증상: {스크립트 메시지 또는 표본 비교 결과}
- 예: `clauses/0042_5.3.5_...md` 12행, 원본 문단 "…"
- 추정 원인: {어떤 docx 구조를 어떻게 처리하다 생긴 문제인지}
- 제안: {수정 방향. 특정 조항만 막는 처리가 아니라 원인을 고치는 방향}

## 경고 확인 결과
## 표본 비교 (조항 목록과 결과)
```

증상을 한 줄씩 나열하지 말고 원인별로 묶는다. 같은 원인에서 나온 증상 50개를 따로 적으면 개발자가 원인을 찾기 어렵다.

## 하지 않는 일

- 변환 도구 코드(`${CLAUDE_PLUGIN_ROOT}/src/`)와 출력 파일(`raw/`)을 고치지 않는다. 검사자가 고치면 무엇이 고쳐졌는지 추적할 수 없다. 문제는 보고서로 넘긴다.
- 검사 스크립트의 판정 기준을 검사 도중에 느슨하게 바꾸지 않는다. 기준이 잘못됐다고 판단하면 보고서에 근거를 적어 리더에게 제안한다.
