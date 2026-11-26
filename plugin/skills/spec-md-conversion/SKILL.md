---
name: spec-md-conversion
description: "3GPP 규격 .docx를 조항(clause) 단위 Markdown raw 파일로 바꾸는 변환 도구 spec2md(Python)를 설계·구현·수정하는 방법과 출력 규약을 다룬다. spec2md 코드 작성, 파서 버그 수정, 표·ASN.1·그림·수식 변환 규칙 변경, 분할 깊이·파일 이름·front matter·manifest 형식 결정, 'spec2md topics' 명령 구현에 사용한다. 이미 만든 출력의 누락 검사는 conversion-check, docx 원본 구조 조사는 3gpp-docx-structure 스킬을 쓴다."
---

# spec2md 변환 도구 구현 가이드

목표는 LLM 위키를 만들기 전 단계의 **raw 파일**이다. 원문 내용을 해석하거나 요약하지 않는다. 구조와 텍스트를 빠짐없이, 재현 가능하게 옮기는 것이 전부다. 요약하거나 표현을 바꾸면 이후 위키 단계에서 원문과 대조할 근거가 사라진다.

출력 형식은 `references/output-contract.md`가 정한다. 코드를 쓰기 전에 반드시 읽는다. 검사 스크립트가 이 규약을 기준으로 판정하므로, 규약에서 벗어나면 변환이 맞아도 검사에 실패한다.

## 프로젝트 구조

```
3gpp-specs/                     # 사용자가 넣어 둔 원본 .docx (읽기 전용으로 취급)
${CLAUDE_PLUGIN_ROOT}/src/spec2md/
├── __init__.py            # __version__
├── __main__.py            # uv run --project "${CLAUDE_PLUGIN_ROOT}" spec2md
├── cli.py                 # convert / batch / topics 하위 명령
├── reader.py              # docx 열기, 스타일 해석, 본문 요소 순회
├── blocks.py              # 문단·표·코드·그림·수식 → 중간 블록
├── render.py              # 블록 → Markdown
├── split.py               # 제목 기준 분할, manifest 생성
└── topics.py              # topics.json → 주제 파일
${CLAUDE_PLUGIN_ROOT}/tests/                     # pytest. 작은 docx 픽스처는 코드로 생성
${CLAUDE_PLUGIN_ROOT}/pyproject.toml, uv.lock  # 의존성 버전 고정 (uv). requirements.txt는 pip 대안용 사본
raw/                       # 출력 (output-contract.md)
```

## CLI

```
uv run --project "${CLAUDE_PLUGIN_ROOT}" spec2md convert 3gpp-specs/38331-i10.docx -o raw/ [--split-depth 3] [--max-chars 60000]
uv run --project "${CLAUDE_PLUGIN_ROOT}" spec2md batch 3gpp-specs/ -o raw/ [--split-depth 3]
uv run --project "${CLAUDE_PLUGIN_ROOT}" spec2md topics raw/38331-i10/
```

- `--split-depth`: 이 레벨 이하의 제목마다 파일을 만든다. 기본값 3. 규격마다 알맞은 값이 다르다. 38.331처럼 깊은 규격은 4가 필요할 수 있다.
- `--max-chars`: 한 파일 본문이 이 값을 넘고 더 깊은 하위 제목이 있으면, 그 파일만 한 단계 더 나눈다. LLM 입력 청크가 지나치게 커지지 않게 하기 위한 장치다.
- 분할 규격: `convert`는 docx를 여러 개 받을 수 있다(`convert 3gpp-specs/36101-j60_*.docx -o raw/`). 같은 규격 코드의 부분 파일이어야 하며, 파일 이름 순서로 이어 붙여 `raw/36101-j60/` 하나를 만든다. `batch`는 출력 규약 1절의 정규식으로 파일을 규격 코드별로 묶어 처리한다.
- `batch`는 한 파일이 실패해도 멈추지 않는다. 실패 목록과 원인을 마지막에 출력하고 종료 코드 1로 끝낸다.

## 구현 원칙

1. **문서 순서대로 한 번만 순회한다.** `w:body`의 자식(`w:p`, `w:tbl`, `w:sdt`)을 순서대로 읽는다. python-docx의 `doc.paragraphs`와 `doc.tables`는 따로 순회하므로 표 위치가 사라진다. python-docx는 패키지·관계(이미지) 접근에만 쓰고, 본문은 `doc.element.body`를 lxml로 직접 순회한다.
2. **스타일 이름으로 판단하고 스타일 ID에 의존하지 않는다.** 스타일 ID는 언어판 Word에 따라 다르다. `styles.xml`에서 ID→이름 표를 만들고 이름(`heading 3`, `B1`, `PL`, `TH`)으로 분기한다. 3GPP 스타일 목록은 `3gpp-docx-structure` 스킬에 있다.
3. **모르는 요소를 조용히 버리지 않는다.** 처리하지 못한 스타일이나 요소는 일반 문단으로 출력하고, 실행이 끝날 때 `unhandled: {style: count}`로 경고한다. 조용히 버리면 검사 스크립트로도 손실을 찾기 어렵다.
4. **결정적(deterministic) 출력.** 같은 입력이면 바이트 단위로 같은 출력을 낸다. 시각, 난수, dict 순서에 의존하지 않는다. 다시 실행한 결과를 diff로 검토하기 위해서다.
5. **대용량 대비.** 38.331 같은 규격은 docx가 수십 MB, 조항이 수천 개다. 블록을 한 번에 문자열로 합치지 말고 조항 단위로 써 나간다. 전체 변환은 몇 분 안에 끝나야 한다.
6. **원본은 읽기만 한다.** `3gpp-specs/`의 파일을 고치거나 옮기지 않는다.
7. **의존성은 최소화하고 버전을 고정한다.** 기본 조합은 `python-docx`, `lxml`이다. pandoc이나 LibreOffice 같은 외부 프로그램은 쓰지 않는다. 이 환경에 설치되어 있지 않기 때문이다.

## 까다로운 부분

| 주제 | 접근 |
| --- | --- |
| 제목 텍스트 | `5.3.5<TAB>RRC reconfiguration`. 첫 탭이나 공백으로 번호와 제목을 나눈다. 부속서 제목은 `Annex A (normative):<TAB>Title`이며 `heading 8`/`heading 9` 스타일이지만 레벨 1이다 |
| 자동 번호 | 3GPP 제목 번호는 대개 텍스트로 들어 있다. `w:numPr` 번호가 있는 문단은 번호 텍스트를 직접 만들어야 하므로, 실제 파일에서 빈도를 확인한 뒤 처리한다 |
| 병합 셀 | `gridSpan` → colspan. `vMerge restart`부터 이어지는 `vMerge` 행 수 → rowspan |
| 표 안의 PL·목록 | HTML 셀 안에서는 `<pre>`와 `<br>`로 표현한다 |
| 그림 | `a:blip r:embed` → 관계 ID → `word/media/…`. 같은 이미지를 여러 번 참조하면 한 번만 복사한다 |
| `w:sdt`, `w:customXml` | 래퍼일 뿐이므로 안쪽 내용을 순회한다 |
| 숨은 텍스트 (`w:vanish`) | 버린다 |
| 특수 문자 | `w:sym`은 해당 유니코드로, 줄 안 `w:br`은 `<br>`(표 안) 또는 줄바꿈으로 바꾼다 |

## 테스트

- 기능마다 작은 docx 픽스처를 코드로 생성해 pytest로 검증한다(병합 표, ASN.1 블록, 부속서 제목, 그림 하나). 실제 규격 파일을 저장소 테스트에 넣지 않는다. 너무 크기 때문이다.
- 실제 규격을 변환한 뒤에는 `conversion-check` 스킬의 검사 스크립트로 확인한다. 테스트 통과만으로 완료를 주장하지 않는다.

## 수정 요청을 받았을 때

- 검사 보고서(`_workspace/*_checker_report*.md`)에 적힌 오류를 원인별로 묶어 고친다. 증상 하나만 막는 특수 처리(`if clause == "5.3.5"`)를 넣지 않는다. 같은 원인이 다른 규격에서도 나타나기 때문이다.
- 출력 규약을 바꿔야 한다면 먼저 리더에게 알린다. 규약은 검사 스크립트와 주제 묶음 단계도 함께 따르기 때문이다.
