---
name: topic-grouping
description: "spec2md로 조항별로 나눈 3GPP 규격 출력(raw/{spec}/manifest.json)을 읽고, 여러 조항을 LLM 위키 항목에 알맞은 주제(topic)로 묶는 topics/topics.json을 작성한다. '주제별로 묶어줘', '토픽 매니페스트 만들어줘', '주제 분류 다시', 조항-주제 매핑 수정에 사용한다. 조항 단위 변환 자체는 spec-md-conversion, 주제 파일 생성 명령 구현도 spec-md-conversion 스킬이 다룬다."
---

# 조항을 주제로 묶기

조항 번호 순서는 규격 편집 구조다. 위키 항목은 개념 단위가 더 유용하다. 예를 들어 RRC 재구성 절차(5.3.5), 메시지 정의(6.2.2), 관련 IE(6.3.x)는 서로 떨어져 있지만 한 주제다. 이 스킬은 그 매핑만 만든다. 조항 원문은 고치거나 요약하지 않는다. 주제 파일은 `uv run --project "${CLAUDE_PLUGIN_ROOT}" spec2md topics raw/{spec}/` 명령이 `topics.json`을 읽어 기계적으로 만든다.

## 입력

- `raw/{spec}/manifest.json`: 조항 번호, 제목, 레벨, 파일
- 필요할 때 조항 파일의 첫 몇 문단. 제목만으로 범위를 알 수 없을 때만 읽는다. 전체를 다 읽으면 큰 규격에서 맥락이 넘친다.

## 묶는 원칙

1. **개념 하나 = 주제 하나.** 절차(procedure), 메시지·IE 정의, 타이머·상수처럼 같은 개념을 서로 다른 장에서 다루면 한 주제로 묶는다. 이유: 위키 항목 하나가 그 개념의 전체 그림을 담아야 한다.
2. **원문 구조가 이미 개념 단위면 그대로 따른다.** 억지로 장을 넘나드는 묶음을 만들지 않는다.
3. **한 조항은 여러 주제에 속할 수 있다.** 공통 정의(예: 일반 절차 원칙)는 관련 주제마다 넣어도 된다. 다만 주제 대부분에 들어가는 조항은 별도의 "general" 주제로 빼고 `related`로 연결한다.
4. **크기를 고려한다.** manifest의 `chars` 합계가 지나치게 큰 주제(예: 200,000자 초과)는 하위 주제로 나누고, 조항 한두 개뿐인 아주 작은 주제는 이웃 주제와 합칠지 검토한다.
5. **상용구 조항은 분류하지 않는다.** Foreword, Scope, References 같은 조항은 `uncategorized`에 넣는다. 억지로 분류하지 않는다.
6. **빠짐없이 처리한다.** 본문이 있는 모든 조항(`file`이 null이 아닌 조항)은 하나 이상의 주제에 들어가거나 `uncategorized`에 들어가야 한다. 마지막에 누락된 조항이 없는지 스크립트로 셀 수 있게 목록을 정확한 조항 번호로 쓴다.
7. **id는 안정적으로 만든다.** 소문자 kebab-case 영어 slug를 쓴다(`rrc-reconfiguration`). 다시 실행할 때 같은 개념에는 같은 id를 유지해 이후 위키 링크가 깨지지 않게 한다.
   **규격이 달라도 같은 개념이면 같은 id를 쓴다.** 새 주제의 id를 정하기 전에 `references/feature-taxonomy.md`의 기능 영역을 보고, 범위가 맞는 영역이 있으면 그 id를 그대로 쓴다. 이유: 위키 feature 페이지 하나가 여러 규격의 같은 주제를 모아야 한다.
8. **제목과 요약은 영어로 쓴다.** 위키 raw 파일 언어와 맞춘다. `summary`는 범위를 한 문장으로만 쓴다. 기술 내용을 해석해 덧붙이지 않는다.

## 출력

`raw/{spec}/topics/topics.json`. 형식은 `spec-md-conversion/references/output-contract.md`의 6절을 따른다.

작성한 뒤 다음 명령으로 확인한다.

```
uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_SKILL_DIR}/scripts/check_topics.py" raw/{spec}
```

종료 코드가 0이어야 한다. 0이 아니면 다음 중 하나가 남아 있다는 뜻이다. 배정되지 않은 조항, manifest에 없는 조항 번호, 잘못된 형식이나 중복된 id. 스크립트가 표시하는 `large`/`tiny` 주제는 원칙 4에 따라 검토한다.

## 다시 실행할 때

기존 `topics.json`이 있으면 읽고, 요청받은 부분만 고친다. 기존 id는 바꾸지 않는다. 주제를 나누거나 합치면 `related`에 이전 id를 남긴다.
