---
name: spec2md-orchestrator
description: "3GPP 규격 .docx를 LLM 위키용 조항·주제별 Markdown raw 파일로 바꾸는 전체 작업을 조율한다. 변환 도구 spec2md 개발, 새 규격 형식 분석, specs/ 일괄 변환, 변환 결과 검사, 주제별 묶음을 하나의 흐름으로 처리한다. '3GPP 규격 md로 변환해줘', 'spec2md 만들어줘', '이 TS 변환', 'raw 파일 생성', '주제별로 묶어줘'에 사용하며, 변환 다시 실행, 재변환, 업데이트, 수정, 보완, '표 변환만 다시', '38.331만 다시', '이전 결과를 바탕으로 개선', 새 Release 파일 추가 같은 후속 요청에도 사용한다. docx 구조 질문 하나에 답하는 정도의 단순 질문에는 직접 답한다."
---

# spec2md 오케스트레이터

3GPP 규격 원본(`specs/*.docx`)에서 LLM 위키를 만들기 전 단계의 raw Markdown(`raw/{spec}/`)을 만든다. 원문을 해석하거나 요약하지 않고 충실하게 옮기는 것이 목표다. 내용이 기술적으로 맞는지는 검증하지 않는다. 다만 변환하면서 조항·표·코드가 빠지지 않았는지는 검사 스크립트로 확인한다. 이 검사는 내용 검증이 아니라 도구가 제대로 동작하는지 확인하는 장치다.

## 실행 모드: 혼합

| 단계 | 실행 모드 | 선택 이유 |
| --- | --- | --- |
| 1. 형식 분석 | 서브에이전트 위임 | 샘플 파일마다 독립 분석이고 보고서만 받으면 된다 |
| 2. 개발·보정 루프 | 지속형 에이전트 협업 | 개발자와 검사자가 라운드마다 이전 맥락을 유지한 채 피드백을 주고받는다 |
| 3. 일괄 변환·검사 | 메인 직접 실행 + 실패 시 서브에이전트 | 변환은 결정적 CLI이므로 에이전트가 필요 없다. 실패 원인 진단만 맡긴다 |
| 4. 주제 묶음(선택) | 서브에이전트 위임, 규격 6개 이상이면 워크플로 조율 | 규격마다 독립 작업이다. 목록이 정해져 있어 많으면 코드로 분산한다 |

이 스킬을 사용자가 불러오면 4단계의 Workflow 사용에 동의한 것으로 본다. 기본 동시 실행은 규격 5개 이하로 제한한다.

## 에이전트 구성

| 이름 | `subagent_type` | 스킬 | 산출물 |
| --- | --- | --- | --- |
| (단발) | `spec-format-analyst` | 3gpp-docx-structure | `_workspace/01_analyst_{spec}_format.md`, `_workspace/01_inspect_{spec}.json` |
| `developer` | `converter-developer` | spec-md-conversion | `src/spec2md/`, `tests/`, `_workspace/02_developer_changes.md` |
| `checker` | `conversion-checker` | conversion-check | `_workspace/02_checker_report_{spec}_r{N}.md` |
| (단발) | `topic-curator` | topic-grouping | `raw/{spec}/topics/topics.json` |

## 경로 규칙

| 경로 | 내용 |
| --- | --- |
| `specs/` | 사용자 원본 docx. 읽기만 한다 |
| `src/spec2md/`, `tests/` | 변환 도구 |
| `raw/{spec}/` | 최종 산출물(출력 규약: `spec-md-conversion/references/output-contract.md`) |
| `_workspace/` | 중간 산출물. `{phase}_{agent}_{artifact}.{ext}`. 사후 확인용으로 남긴다 |

`{spec}`은 규격 코드다. docx 파일 이름에서 확장자를 빼고, 분할 파일 접미사가 있으면 그것도 뺀다(`38331-i10`, `36101-j60_s00-07.docx` → `36101-j60`). 같은 코드의 분할 파일들은 하나의 규격으로 합쳐 변환한다(출력 규약 1절). 분석·검사에서 분할 규격을 다룰 때는 모든 부분 파일을 함께 넘긴다(`inspect_docx.py P1.docx P2.docx …`).

## 작업 절차

### 0단계: 요청 분류와 기존 작업 확인

다음을 확인한다: `src/spec2md/`가 있는가, `specs/`의 docx 목록, `raw/`의 기존 출력, `_workspace/`.

| 상황 | 진행 |
| --- | --- |
| 도구가 없음 | 1 → 2 → 3 (→ 4는 요청 시) |
| 도구가 있고 새 규격만 변환 | 3. 형식이 낯선 규격(새 Release, 다른 WG)이면 그 파일만 1을 먼저 실행 |
| 특정 변환 규칙 수정 요청("표 변환 고쳐줘") | 2를 해당 규칙 범위로만 실행 → 3을 영향받는 규격만 |
| 특정 규격만 다시("38.331만") | 3을 `--only`로 실행 |
| 주제 묶음만 요청 | 4. 이미 `topics.json`이 있으면 기존 결과를 고치는 작업이다 |
| `_workspace/`가 있고 완전히 새 입력 세트 | 기존 `_workspace/`를 `_workspace_{YYYYMMDD_HHMM}/`로 옮기고 새로 시작 |

`specs/`가 비어 있으면 사용자에게 docx를 `specs/`에 넣어 달라고 요청하고 멈춘다.

### 1단계: 형식 분석

**실행 모드:** 서브에이전트 위임

1. 샘플을 고른다. 기본 1~3개를 고르되, 크기가 가장 큰 규격, 성격이 다른 규격(예: 절차 중심 TS 38.331, 개요 중심 TS 38.300), 아직 분석하지 않은 Release를 우선한다.
2. 한 메시지에서 샘플마다 Agent를 병렬로 호출한다. `name`은 지정하지 않는 단발 실행이다.
   - `subagent_type: "spec-format-analyst"`
   - `prompt`: "specs/{file}.docx를 3gpp-docx-structure 스킬로 분석하라. _workspace/01_inspect_{spec}.json과 _workspace/01_analyst_{spec}_format.md를 만들어라. 출력 규약은 .claude/skills/spec-md-conversion/references/output-contract.md다."
3. 완료 알림을 기다린다. 보고서들이 출력 규약 변경을 제안하면 메인이 판단해 규약을 고치고, 그 사실을 사용자에게 한 줄로 알린다. 규약을 고치면 `check_output.py`가 규약과 계속 맞는지도 함께 확인한다.

### 2단계: 개발·보정 루프

**실행 모드:** 지속형 에이전트 협업

1. 한 메시지에서 두 에이전트를 실행한다.
   - `Agent(name: "developer", subagent_type: "converter-developer", prompt: "spec-md-conversion 스킬과 출력 규약을 따라 src/spec2md/를 구현(또는 {수정 범위}를 수정)하라. 근거: _workspace/01_analyst_*_format.md. 샘플: {샘플 목록}. 샘플 출력은 _workspace/02_sample_out/에. 첫 메시지로 쓸 수 있는 도구 목록을 알려라.")`
   - `Agent(name: "checker", subagent_type: "conversion-checker", prompt: "conversion-check 스킬로 검사할 준비를 하라. 원본 구조 보고서는 _workspace/01_inspect_*.json이다. 리더가 Round 검사를 지시할 때까지 대기하라. 첫 메시지로 쓸 수 있는 도구 목록을 알려라.")`
2. 작업을 등록한다. 지연 로딩 도구가 빠진 에이전트가 있으면 리더가 상태를 대신 갱신한다.
   - `TaskCreate({title: "Round 1 구현", assignee: "developer"})`
   - `TaskCreate({title: "Round 1 검사", assignee: "checker", depends_on: [Round 1 구현]})`
3. 라운드를 반복한다.
   - developer가 "Round N 완료"를 보내면 → `SendMessage({to: "checker"}, "Round N 검사: 출력 _workspace/02_sample_out/{spec}/, 보고서는 _workspace/02_checker_report_{spec}_rN.md")`
   - checker가 결과를 보내면 → FAIL이거나 확인하지 않은 경고가 있으면 `SendMessage({to: "developer"}, "Round N 보고서 _workspace/02_checker_report_*_rN.md의 원인 1~k를 고쳐라")`
   - 종료 조건: 모든 샘플이 PASS이고, 남은 경고마다 정상인 이유가 보고서에 적혀 있다.
   - 상한: 기본 4라운드. 4라운드가 지나도 같은 ERROR가 남으면 멈추고, 남은 문제와 두 에이전트의 견해를 사용자에게 보고한다. 같은 원인이 되풀이되는 것은 규칙을 바꿀지 사용자가 정해야 하는 신호다.
4. 동결한다. 두 에이전트에게 "Round N 결과로 도구를 동결한다. 이후 수정 사항은 리더에게 먼저 알려라"를 보낸다. 그런 다음 `python -m pytest -q`를 직접 실행해 결과를 확인하고, `src/spec2md/`의 해시를 `_workspace/freeze_02.sha`에 기록한다(`Get-FileHash src/spec2md/*.py` 또는 `sha256sum`).

### 3단계: 일괄 변환·검사

**실행 모드:** 메인 직접 실행. 실패한 규격만 서브에이전트에 위임한다.

1. 동결 해시가 그대로인지 확인한 뒤 변환한다.
   ```
   python -m spec2md batch specs/ -o raw/ --split-depth {1단계 권장값}
   ```
   권장 깊이가 규격마다 다르면 `convert`로 규격별로 실행한다.
2. 전체를 검사한다.
   ```
   python .claude/skills/spec2md-orchestrator/scripts/check_all.py --specs specs --raw raw --ws _workspace --phase 03
   ```
3. FAIL·NO_OUTPUT·CHECK_ERROR가 있는 규격만 `subagent_type: "conversion-checker"`로 단발 진단을 맡긴다(규격이 여럿이면 한 메시지에서 병렬로 호출). 보고서는 `_workspace/03_checker_report_{spec}.md`에 쓰게 한다.
4. 진단 결과 도구를 고쳐야 하면 2단계로 돌아간다. developer가 아직 살아 있으면 SendMessage로 이어서 지시하고, 종료됐으면 같은 유형을 새 이름(`developer2`)으로 실행한 뒤 변경 요약 경로를 넘긴다. 수정한 뒤에는 영향받는 규격만 `--only`로 다시 검사한다. 원래 PASS였던 규격도 하나 이상 다시 검사해 회귀가 없는지 확인한다.

### 4단계: 주제 묶음(선택)

**실행 모드:** 규격 5개 이하면 서브에이전트 위임, 6개 이상이면 워크플로 조율

사용자가 주제별 묶음을 요청했을 때만 실행한다. 3단계에서 PASS한 규격만 대상으로 한다.

- **5개 이하**: 한 메시지에서 규격마다 `Agent(subagent_type: "topic-curator", prompt: "topic-grouping 스킬로 raw/{spec}/topics/topics.json을 작성하고 check_topics.py로 확인하라")`를 호출한다.
- **6개 이상**: Workflow에 다음 스크립트를 넘기고 `args: { specs: [PASS한 규격 코드 배열] }`을 전달한다.

```javascript
export const meta = {
  name: 'spec2md-topics',
  description: '변환된 3GPP 규격마다 topic-curator로 topics.json을 만들고 확인 스크립트로 검사한다',
  phases: [{ title: '주제 묶음' }],
}
const RESULT = { type: 'object', required: ['spec', 'ok', 'topics', 'assigned', 'uncategorized'],
  properties: { spec: { type: 'string' }, ok: { type: 'boolean' }, topics: { type: 'integer' },
    assigned: { type: 'integer' }, uncategorized: { type: 'integer' }, notes: { type: 'string' } } }

phase('주제 묶음')
const results = await pipeline(args.specs, s =>
  agent(`topic-grouping 스킬에 따라 raw/${s}/manifest.json을 읽고 raw/${s}/topics/topics.json을 작성하라. ` +
        `python .claude/skills/topic-grouping/scripts/check_topics.py raw/${s} 결과의 종료 코드가 0이면 ok=true다. ` +
        `spec 필드에는 '${s}'를 그대로 넣어라.`,
    { agentType: 'topic-curator', label: `topics:${s}`, phase: '주제 묶음', schema: RESULT }))
const done = results.filter(Boolean)
const failed = args.specs.filter(s => !done.some(d => d.spec === s && d.ok))
log(`규격 ${args.specs.length}개 중 ${done.length}개 응답, 확인 실패·누락 ${failed.length}개`)
return { done, failed }
```

완료 알림을 받은 뒤 `ok`인 규격마다 `python -m spec2md topics raw/{spec}/`를 실행해 주제 파일을 만든다. 워크플로 `runId`는 `_workspace/run_meta.json`에 기록한다. 일부만 다시 실행할 때 `resumeFromRunId`로 재개할 수 있다.

### 5단계: 보고

사용자에게 다음을 알린다: 변환한 규격 수와 PASS 수, 규격별 파일 수와 파일 크기 범위, 남은 경고와 정상으로 본 이유, 실패·누락 규격과 원인, 주제 묶음 결과(실행한 경우), 산출물 위치. `_workspace/`는 지우지 않는다.

## 오류 처리

| 상황 | 대응 |
| --- | --- |
| 서브에이전트 하나 실패 | 한 번 다시 시도한다. 또 실패하면 그 규격을 제외하고 진행하고, 보고서에 누락을 적는다 |
| developer·checker 무응답 | SendMessage로 상태를 확인하고 다시 지시한다. 그래도 실패하면 같은 유형을 새 이름으로 실행하고 `_workspace/02_*` 경로를 넘긴다 |
| 사용량 한도, 인증 만료, 권한 거부 | 다시 시도하지 않는다. 부분 산출물을 직접 열어 실제로 어디까지 진행됐는지 확인하고 `_workspace/blocked.md`에 기록한 뒤 보고한다. 사용량 한도라면 풀리는 시각도 알린다. 에이전트의 판단을 추측해 채우지 않는다 |
| `pip install` 실패 | 오류 원문을 사용자에게 보여 주고 네트워크·권한 문제인지 묻는다. 표준 라이브러리 우회 구현은 사용자가 동의할 때만 한다 |
| docx가 열리지 않음(손상, 실제로는 .doc) | 그 파일만 제외하고 보고한다. 형식 변환은 시도하지 않는다(LibreOffice 없음) |
| 워크플로 결과 일부 `null` | `.filter(Boolean)`으로 제외하고 `failed` 목록을 보고한다. 빈 결과를 성공으로 판단하지 않는다 |
| 검사 기준과 규약이 충돌 | 기준을 조용히 느슨하게 바꾸지 않는다. 규약을 고칠지 결정한 뒤 규약과 스크립트를 함께 고친다 |

## 테스트 시나리오

### 정상 흐름
1. 사용자가 `specs/`에 `38331-i10.docx`와 `38300-i00.docx`를 넣고 "spec2md 만들어서 변환해줘"라고 요청한다.
2. 0단계에서 도구가 없음을 확인하고, 1단계에서 두 파일을 병렬로 분석한다(권장 깊이 38331=4, 38300=3).
3. 2단계에서 developer가 구현한다. Round 1 검사에서 병합 표 ERROR가 나오고 Round 2에서 PASS한 뒤 동결한다.
4. 3단계 `check_all.py`에서 2/2 PASS가 나온다.
5. 예상 결과: `raw/38331-i10/`, `raw/38300-i00/`에 `manifest.json`과 `clauses/*.md`가 생기고 `_workspace/03_check_summary.json`이 남는다.

### 오류 흐름
1. 3단계에서 `38213-i20`이 FAIL(ASN1START 수 불일치)이다.
2. checker 단발 진단 결과, 표 셀 안 PL 문단을 놓쳤다는 원인이 나온다.
3. 2단계로 돌아가 developer(종료됐다면 `developer2`)가 고치고, `--only 38213-i20,38331-i10`으로 다시 검사해 회귀가 없는지 확인한다.
4. 최종 보고에 "38213-i20: 1회 재작업(표 안 코드 블록)"이라고 적는다.
