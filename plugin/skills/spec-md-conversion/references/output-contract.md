# spec2md 출력 규약 (Output Contract)

변환 도구(`spec2md`), 검사 스크립트(`conversion-check/scripts/check_output.py`), 주제 묶음(`topic-grouping`), 링크 검사기(`spec-linking/scripts/check_links.py`)가 모두 이 규약을 기준으로 동작한다. 규약을 바꾸면 해당하는 곳을 함께 고친다. 하나만 고치면 검사가 거짓 실패하거나 거짓 통과한다.

## 목차
1. 디렉터리 구조
2. 파일 이름
3. Front matter
4. manifest.json
5. 본문 변환 규칙
6. topics.json과 주제 파일
7. linked/ 출력

---

## 1. 디렉터리 구조

```
raw/{docx 파일 이름에서 확장자 뺀 값}/   예: 3gpp-specs/38331-i10.docx → raw/38331-i10/
├── manifest.json                      # 조항 목록과 통계 (필수)
├── clauses/                           # 조항 단위 Markdown (필수)
│   ├── 0001_foreword.md
│   ├── 0042_5.3.5_rrc-reconfiguration.md
│   └── ...
├── media/                             # docx에서 추출한 이미지 원본 (그림이 있을 때)
│   └── image12.emf
└── topics/                            # 선택: 주제 묶음 (topic-grouping 실행 후)
    ├── topics.json
    └── rrc-reconfiguration.md
```

- 출력 폴더 이름은 **규격 코드**다. 규격 코드는 docx 파일 이름에서 확장자를 빼고, 분할 파일 접미사가 있으면 그것도 뺀 값이다. 파일 이름이 3GPP 규칙과 달라도 그 밖의 부분은 바꾸지 않는다. 검사 스크립트(`check_all.py`)가 이 이름으로 출력을 찾기 때문이다.
- **분할 규격(multi-part).** 큰 규격은 여러 docx로 나뉘어 배포된다(`36101-j60_cover.docx`, `36101-j60_s00-07.docx`, `36101-j60_s08-XX.docx`, `36101-j60_sAnnexes.docx`, `38101-1-j70_0_cover.docx` …). 파일 이름이 정규식 `^(\d{5}(?:-\d+)?-[0-9a-z]\d{2})_(.+)$`에 맞으면 1번 그룹이 규격 코드이고 2번 그룹이 부분(part) 이름이다. 같은 코드의 파일은 **파일 이름의 단순 정렬 순서(대소문자 구분, `sorted()`)**로 이어 붙여(단, 부분 이름이 `숫자_`로 시작하면(`38133-j60_10_sA0606-sA0611`) 그 숫자는 정수로 비교해 `_2_`가 `_10_` 앞에 온다) 하나의 문서처럼 변환하고 출력은 `raw/{코드}/` 하나로 만든다. `order`는 부분을 이어 가며 1부터 계속 증가한다. 부분 경계에서 조항이 끊기지 않는다고 가정하지 않는다. 앞 부분의 마지막 조항이 다음 부분의 첫 제목 전까지 이어진다.
  - 버전 정보는 `_cover` 부분의 표지를 우선한다. 각 부분의 표지·목차는 모두 건너뛰고 `skipped`에 `"{part}: cover"`처럼 부분 이름과 함께 기록한다.
  - 정규식에 맞지 않는 파일 이름은 그 자체(확장자 제외)가 코드인 단일 파일 규격이다.
  - **media 이름 충돌.** 부분마다 `image1.wmf`부터 번호가 다시 붙는다. 분할 규격의 media는 `media/{part}_{원래 이름}`(`media/s08-XX_image12.wmf`)으로 저장한다. 단일 파일 규격은 `media/{원래 이름}` 그대로다. 같은 이미지를 여러 번 참조하면 한 번만 복사한다.
  - 스타일(`styles.xml`)은 부분마다 다르므로 부분마다 따로 읽는다.
- `spec`, `version`, `release` 값은 파일 이름(3GPP 규칙일 때)이나 표지(cover)의 `3GPP TS 38.331 V18.1.0`에서 읽는다. 둘이 다르면 표지를 따르고 경고를 출력한다.
- 버전 코드 문자: `0-9` 다음 `a=10, b=11, … i=18, j=19 …`. `i10` → `18.1.0`. 메이저 번호가 Release 번호다(`Rel-18`).

## 2. 파일 이름

`{order:04d}_{clause}_{slug}.md`

- `order`: 문서 등장 순서(1부터). 파일 탐색기에서 원문 순서대로 정렬되게 한다.
- `clause`: 조항 번호(`5.3.5`, `A.2`). 번호 없는 제목(Foreword, Introduction)은 이 부분을 생략하고 `0001_foreword.md`처럼 쓴다.
- `slug`: 제목을 소문자로 바꾸고 영숫자 외 문자를 `-`로 바꾼 값. 60자에서 자른다.

## 3. Front matter

모든 조항 파일은 YAML front matter로 시작한다. 값은 한 줄 스칼라만 쓴다(검사 스크립트가 PyYAML 없이 읽는다). `path`만 예외로 JSON 배열 한 줄을 쓴다.

```yaml
---
spec: "TS 38.331"
spec_number: "38.331"
version: "18.1.0"
release: "Rel-18"
clause: "5.3.5"
title: "RRC reconfiguration"
level: 3
parent: "5.3"
path: ["5 Procedures", "5.3 Connected mode", "5.3.5 RRC reconfiguration"]
source_file: "38331-i10.docx"
---
```

- 필수 키: `spec`, `version`, `clause`, `title`, `level`, `source_file`.
- **제목 해석 규칙.** 기준 구현은 `3gpp-docx-structure/scripts/inspect_docx.py`의 `para_style`·`parse_clause`·`clause_level`·`clause_parent`다. 변환기는 이 함수들과 같은 결과를 내야 한다(검사 스크립트가 이 결과와 대조한다).
  - 제목 문단: 스타일 이름 `heading N`, `Header N`(38.101-5의 사용자 정의 제목 스타일, `outlineLvl` 없음), 3GPP 전용 `H6`(정의상 `outlineLvl` 9이지만 6수준 조항), 또는 문단·스타일 `outlineLvl` 0~8. 쪽 머리글 스타일 `header`(번호 없음)는 제목이 아니다. `outlineLvl` 9는 '본문'이므로 제목이 아니다. **표 셀 안의 제목 스타일 문단은 제목이 아니다**(분할 기준이 아님, 본문으로 출력).
  - 제목 텍스트: `w:t`와 수식 `m:t` 텍스트를 이어 붙이고(제목 안 수식은 LaTeX가 아니라 평문), 줄바꿈(`w:br`)은 공백 하나로 접는다. `Annex A (normative): <br>Measurement channels` → clause `A`, title `Measurement channels`.
  - 조항 번호 정규식: `^\s*((?:[A-Z]{1,2}|\d+[A-Za-z]{0,2}\d*)(?:\.(?:\d+[A-Za-z]{0,2}\d*|[A-Z]))*)\.?:?[\s ]+(.+)$` (첫 성분이 숫자이거나 점이 있어야 번호로 인정). `4.3A`, `9.4.1a`, `5.3.5.13b1`, `B.2.3B.4A`, `F.5.F`, 끝의 점(`6.3.3.1.`), 번호 뒤 콜론(`A.1:<TAB>Title`, 38.306), NBSP 구분을 처리한다.
  - **level**: 부속서 제목(`Annex X`)은 1. 번호 있는 조항은 **번호 깊이**(점 개수 + 1)다. 스타일 수준이 아니다. 3GPP는 부속서 `A.1`에 `heading 1`을 쓰고, 본문에서도 스타일과 번호 깊이가 어긋나는 일이 흔하기 때문이다. 번호 없는 제목만 스타일 수준을 쓴다.
  - **parent**: 번호에서 마지막 성분을 뗀 값(`5.3.5` → `5.3`, `A.1` → `A`). 최상위는 null. 번호 없는 제목의 parent는 바로 앞의 더 얕은 제목의 clause다.
  - 번호 없는 IE·필드 제목(38.331 `–<TAB>RRCReconfiguration`): 앞의 대시(`–`, `-`)와 공백은 표지이므로 title에서 뗀다. clause는 title의 slug다.
  - 원문 오타 보정 하나: 점 뒤에 공백이 들어가 번호가 갈라진 `5. 2.2.4.2.3<TAB>Title`(36.133), `10.1. 38A.1<TAB>Introduction`·`A.6. 11.3.1.3<TAB>Test requirements`(38.133)는 탭 앞의 두 조각이 모두 번호(앞 조각은 한 성분이거나 `10.1`·`A.6` 같은 여러 성분, 뒤 조각은 `38A.1`처럼 문자 접미 성분 포함 가능)이고 뒤 조각에 점이 있을 때만 `5.2.2.4.2.3`, `10.1.38A.1`, `A.6.11.3.1.3`으로 붙인다(기준: `inspect_docx.py`의 `SPLIT_NUM_RE`). `5.<TAB>Scope`, `5 General`은 그대로다.
  - 원문에 같은 번호가 두 번 나와도(원문 오류) 둘 다 출력한다. 파일 이름에 `order`가 있어 충돌하지 않는다.
- `source_file`은 그 조항 제목이 들어 있던 docx 파일 이름이다. 분할 규격이면 부분 파일 이름(`36101-j60_s08-XX.docx`)이 된다.
- 번호 없는 제목의 `clause`는 제목 slug(`foreword`)를 쓴다. 검사 스크립트도 같은 방식으로 원문 제목과 대조한다.
- 부속서(Annex)의 `clause`는 문자(`A`)이고 `level`은 1이다. 하위 조항은 `A.1`, `A.1.2`.
- 인코딩은 UTF-8(BOM 없음), 줄바꿈은 LF.

## 4. manifest.json

```json
{
  "spec": "TS 38.331", "spec_number": "38.331",
  "version": "18.1.0", "release": "Rel-18",
  "source_files": ["38331-i10.docx"],
  "tool_version": "0.1.0",
  "split_depth": 3,
  "skipped": ["cover", "contents"],
  "clauses": [
    {"order": 42, "clause": "5.3.5", "title": "RRC reconfiguration", "level": 3,
     "parent": "5.3", "source_file": "38331-i10.docx",
     "file": "clauses/0042_5.3.5_rrc-reconfiguration.md",
     "tables": 2, "figures": 1, "code_blocks": 3, "equations": 0, "chars": 18234}
  ]
}
```

- `--max-chars` 때문에 더 깊게 나뉜 하위 조항도 `clauses`에 원문 순서대로 들어간다(`level > split_depth`). 이런 항목에는 `"auto_split": true`를 붙인다. 하위 제목이 없어 더 나눌 수 없는 말단 조항은 크기와 상관없이 파일 하나로 둔다. 표를 행 단위로 나누지 않는다(검사기가 크기 경고만 낸다).
- `equations`는 OMML 수식 수와 OLE 수식 개체(`Equation.*`) 수의 합이다. OLE 수식은 그림으로 세지 않는다(`figures`에서 뺀다).
- `clauses`에는 `level <= split_depth`인 **모든** 제목을 원문 순서대로 넣는다. 본문이 없는 제목(바로 하위 조항이 시작되는 상위 제목, `Void` 조항)도 넣되 `"file": null`로 둔다. 빈 파일을 만들지 않으면서도 구조는 잃지 않기 위해서다.
- `source_files`는 이 규격을 이룬 docx 파일 이름 목록이다(이어 붙인 순서). 단일 파일 규격도 원소 하나짜리 배열로 쓴다. 각 조항 항목의 `source_file`은 front matter의 값과 같다.
- `tables`, `figures`, `code_blocks`, `equations`는 그 파일에 들어간 개수다. 표지·목차·변경 이력 부속서를 건너뛰었다면 `skipped`에 적는다.
- 실행할 때마다 값이 달라지는 필드(생성 시각 등)는 넣지 않는다. 같은 입력이면 같은 출력이 나와야 재실행 결과를 diff로 비교할 수 있다.

## 5. 본문 변환 규칙

원칙: 원문 요소를 **문서 순서 그대로** 출력한다. 캡션을 앞뒤로 옮기거나 요소 순서를 바꾸지 않는다.

| 원문 요소 | Markdown 출력 | 이유 |
| --- | --- | --- |
| 분할 기준 제목 | 파일 첫 줄 `# 5.3.5 RRC reconfiguration` | 파일마다 제목이 자기 완결적이어야 한다 |
| 분할 깊이보다 깊은 제목 | 상대 레벨 `##`, `###` … (최대 `######`) | 파일 안 구조 보존 |
| 일반 문단 | 문단 그대로, 문단 사이 빈 줄 | |
| B1~B9 목록 문단 | `(n-1)*2`칸 들여쓰기 + 원문 표지(`-`, `1>`, `a)`)를 **그대로** 유지 | 38.331 절차의 `1>`/`2>` 중첩이 의미를 가진다. 임의로 `-`로 바꾸면 의미가 사라진다. 38.331은 B6~B9도 쓴다 |
| NO (NOTE), NF(그림 아래 NOTE), `Editor's Note` | `> NOTE: …` 인용 블록(원문 텍스트 그대로) | |
| EX/EW (정의·약어) | 탭이 있으면 `- **RRC**: Radio Resource Control`, 탭이 없으면 `- **용어**` | 탭으로 나뉜 용어와 정의 |
| TH (표·블록 제목) | 텍스트가 있으면 그 자리에 `**…**` 한 줄. **다음 요소가 무엇이든**(표, ASN.1 블록, 그림) 같다. 텍스트가 없는 TH는 텍스트를 내지 않되, 안에 든 그림·OLE는 출력한다 | 38.331에서 TH 대부분은 ASN.1 블록 제목이고, 빈 TH는 그림을 담는다 |
| TF (그림 제목) | 그 자리에 `*Figure …*` 한 줄. 앞 요소가 그림이든 표(24.501 IE 비트맵 표)이든 같다 | |
| 표 — 파이프 표 조건 | 병합(gridSpan·vMerge)·gridBefore/gridAfter·중첩 표·셀 안 PL/그림/OLE가 **모두 없으면** GFM 파이프 표. 셀 안 여러 문단은 `<br>`로 잇는다. 셀 내부 `\|`는 `\|`로 이스케이프. 첫 행을 머리글로 쓴다 | 38.331의 1열 필드 설명 표 700여 개를 읽기 쉽게 둔다 |
| 표 — 그 밖 | HTML `<table>`. gridSpan → `colspan`, vMerge → `rowspan`, gridBefore/gridAfter는 빈 `<td>`로 채워 `tblGrid` 열 수를 맞춘다. 셀 안 문단은 `<br>`, 셀 안 PL은 `<pre>`, 그림·OLE는 `<img src="../media/…" alt="…">`(Markdown 이미지 문법은 HTML 안에서 렌더링되지 않음), 수식은 `$…$` | 파이프 표는 병합을 표현하지 못해 행과 열이 어긋난다 |
| 표 셀 안 `toc N`·제목 스타일 문단 | 일반 셀 텍스트 | 36.101 표 안에 실제 데이터가 있다 |
| 표 셀 안 B1~B9 | 표지는 유지하고 `<br>`로 잇는다. 들여쓰기는 셀 안에서 표현하지 않는다(알려진 한계) | |
| PL (코드·ASN.1·ABNF) | 연속 PL 문단을 하나의 펜스 블록으로. `::=`나 `ASN1START`가 있으면 ` ```asn1 `, 아니면 ` ```text ` | |
| `-- ASN1START` / `-- ASN1STOP` | 펜스 안에 **그대로** 유지 | 후속 ASN.1 추출 도구가 이 표지를 기준으로 동작한다 |
| 이미지 (drawing/pict) | `media/`로 원본 추출, `![Figure](../media/imageN.ext)` | EMF/WMF는 변환하지 않고 원본을 둔다(변환 도구 없음) |
| OLE 개체(Visio, Mscgen 등) | 미리보기 이미지가 있으면 이미지로, 없으면 `[embedded object: ProgID]` | |
| OLE 수식(`Equation.3`, `Equation.DSMT4`) | 개체의 `Equation Native` 스트림(MTEF v3/v5)을 해석해 LaTeX로 낸다. 자리와 구분은 OMML과 같다(인라인 `$…$`, 수식만 있는 일반 문단은 `$$…$$`, 표 안은 `$…$`). 바로 뒤에 미리보기 경로를 주석으로 남긴다: `$…$<!-- ole-equation: ../media/s08-XX_image95.wmf -->`. 해석하지 못하면 미리보기 이미지만 `![equation](../media/…)`(표 안은 `<img alt="equation">`). 모두 `equations`로 센다. manifest 최상위에 `"ole_equations": {"latex": n, "image_only": m}`을 기록한다 | 텍스트만 뽑으면 `- and are given by`처럼 빈칸이 남고, 이미지는 위키 단계 LLM이 읽지 못한다. 사용자 결정(2026-11-25) |
| 수식 (OMML) | LaTeX. 문단 안 `m:oMath`(앞뒤에 텍스트가 있음)는 `$…$`. 본문의 `m:oMathPara`나 수식만 있는 문단은 `$$…$$` 블록. 표 셀 안에서는 항상 `$…$`. 행렬 `m:m`은 괄호에 따라 `bmatrix`/`pmatrix`/`matrix`, 한쪽만 열린 `{` + 행렬은 `cases`. 변환할 수 없는 요소가 있으면 `[equation]`을 두고 경고를 낸다 | 개수를 manifest에 기록해 손실을 추적한다 |
| 수식 세부 | B1~B9·NOTE·EX/EW·TH/TF 문단 안 수식은 수식만 있어도 인라인 `$…$`(줄 구조 보존). 인접한 인라인 수식 사이에는 공백 하나(`$a$ $b$`, `$$`로 오인 방지). 수식 텍스트 앞뒤 공백은 `$` 바깥으로 낸다(`port $p$`). 인라인 수식(OMML·OLE)의 앞이나 뒤(주석 뒤)에 영숫자가 공백 없이 붙어 있으면 공백 하나를 넣는다(`where $n$`, `$x$<!-- … --> is`). 구두점 앞에는 넣지 않는다. 내용이 빈 행렬·묶음(`\begin{matrix}\end{matrix}`, 끝의 `{}`)은 내지 않는다. HTML 셀 안 LaTeX는 `&`·`<`를 `&amp;`·`&lt;`로 이스케이프한다 | |
| EQ 문단 | 탭을 버리고 안의 수식·OLE·텍스트를 위 규칙으로 출력 | |
| 자동 번호 문단(`w:numPr`) | 번호 텍스트를 만들지 않고 `- ` 표지를 붙인다(목록 수준 `ilvl`에 따라 `ilvl*2`칸 들여쓰기) | 3GPP는 번호를 텍스트로 넣는 것이 원칙이라 드물다(36.101 약 19개) |
| 텍스트 상자·도형(`w:txbxContent`, 이미지 없는 DrawingML) | 이미지가 있으면 이미지만. 이미지가 없으면 별도 줄에 `[drawing: 안의 글]`. TH/TF 텍스트에 합치지 않는다. `mc:AlternateContent`는 `mc:Choice`만 읽고 `mc:Fallback`은 버린다. 한 문단 안 같은 이미지(rId)는 한 번만 출력 | 이중 출력과 캡션 오염 방지 |
| 아래첨자·위첨자 (`w:vertAlign`) | `<sub>…</sub>`, `<sup>…</sup>` | 떼면 `2^24`가 `224`가 되어 의미가 바뀐다 |
| `w:sym`, Symbol·Wingdings 글꼴 문자 | 해당 유니코드로 매핑(Symbol 글꼴 표 F020–F0FF → 그리스 문자·수학 기호). 매핑하지 못하면 원래 코드를 남기고 경고 | 사용자 정의 영역 문자(U+E000–F8FF)가 남으면 검사기가 경고한다 |
| `w:noBreakHyphen` / `w:softHyphen` | `-` / 버림 | |
| 문단 안 래퍼(`w:hyperlink`, `w:smartTag`, run 수준 `w:sdt`, `w:customXml`, `w:fldSimple`) | 안쪽 run을 순회한다 | 순회하지 않으면 텍스트가 사라진다 |
| 변경 추적 | `w:ins`는 반영, `w:del`은 버림 | 발행본 기준 내용 |
| 필드 | TOC 필드는 버림, 상호 참조는 표시 텍스트만 | |
| 표지·목차 | 첫 제목 이전의 내용(표지 표, ZA/ZT 등)과 본문 `toc N`·`TT` 문단은 건너뛰고 `skipped`에 기록. 버전은 표지 ZA 문단(표 셀 안일 수 있음, run을 모두 이은 뒤) `3GPP\s+T[SR]\s+(\d+\.\d+(?:-\d+)?)\s+V(\d+)\.(\d+)\.(\d+)`로 읽는다 | 위키 raw에 불필요한 상용구 |
| 변경 이력 부속서(Change history) | 제목이 `Change history`(대소문자 무시, 끝 `:` 무시)인 조항과 그 아래 내용·하위 제목을 모두 건너뛰고 manifest에 넣지 않는다. `skipped`에 `"change history"`(분할 규격은 `"{part}: change history"`)로 기록한다. 검사기는 이 조항을 원본 개요에서 빼고, `inspect_docx.py`의 `tables.change_history`만큼 표 수를 뺀다 | CR 목록이라 위키 raw에 불필요하다. 사용자 결정(2026-11-27) |

출력에는 XML 조각(`<w:`), 제어 문자(`\x07`, `\x0b`), 대체 문자(`�`)가 남아 있으면 안 된다.

## 6. topics.json과 주제 파일

`topic-grouping` 스킬을 따르는 에이전트가 `topics/topics.json`을 쓰고, 변환 도구의 `spec2md topics` 명령이 이를 읽어 주제 파일을 만든다.

```json
{
  "spec": "TS 38.331", "version": "18.1.0",
  "topics": [
    {"id": "rrc-reconfiguration", "title": "RRC Reconfiguration",
     "summary": "One-sentence scope of the topic.",
     "clauses": ["5.3.5", "5.3.5.1", "6.2.2"],
     "related": ["rrc-connection-establishment"]}
  ],
  "uncategorized": ["4.1"]
}
```

- 주제 파일 `topics/{id}.md`: front matter(`spec`, `version`, `topic`, `title`, `clauses`) 다음에 지정 조항 파일 본문을 순서대로 이어 붙인다. 각 조항 앞에 `<!-- source: clauses/0042_5.3.5_rrc-reconfiguration.md -->` 주석을 둬 출처를 남긴다.
- 조항 파일 원문은 고치지 않는다. 주제 파일은 언제든 `topics.json`에서 다시 만들 수 있는 파생물이다.

## 7. linked/ 출력

`spec2md link raw -o linked`가 `raw/`를 읽어 `linked/`를 만든다. `raw/`는 바뀌지 않으며, `linked/`는 raw 파일에 링크·앵커·역참조만 더한 사본이다. 검사기 `spec-linking/scripts/check_links.py`는 이 절을 기준으로 변환을 되돌려 raw와 바이트 단위로 비교한다.

```
linked/
├── index.json                  # 전체 목적지 색인
└── {spec}/
    ├── manifest.json           # raw manifest + "link": {"refs": {status별 개수}}
    ├── refs.json               # 찾은 참조 전체와 해석 결과
    └── clauses/*.md            # raw와 같은 파일 이름
```

**앵커.** 표·그림 캡션 줄과 파일 안 하위 제목 줄 바로 앞에 한 줄을 넣는다: `<a id="table-10.1-1"></a>`, `<a id="figure-…"></a>`, `<a id="clause-5.1.2"></a>`. 줄 전체가 앵커이며 뒤에 빈 줄을 두지 않는다. 파일 맨 위가 목적지인 조항은 앵커 없이 파일 경로만 링크한다.

- 캡션 줄: 줄 앞이 `Table`·`Tables`·`Figure`·`Figures`·`Fig.`이고 굵게(`**`)·기울임(`*`)·인용(`> `)이 앞에 올 수 있다. 단어와 번호 사이는 공백(NBSP 포함)이나 콜론(`Table: 5.3.3-2`)이고 붙여 쓰기도 한다(`Table5.2.3.1.16-4`). 꾸밈이 없으면 번호 뒤 콜론이 있거나, 앞뒤가 빈 줄인 단독 문단에서 대문자·괄호로 시작해 문장 부호로 끝나지 않는 제목이 이어져야 한다(`Table 9.7.2.1-2 Minimum requirement (FDD …)`). 원문이 캡션에 제목 수준을 준 `# Table 6.1-1: …` 제목 줄도 콜론이 있으면 캡션이다. 번호 안의 공백과 하이픈 앞 점(`A.5.2.3.1 -1`, `A.9.6.1.1.-2`)은 색인 키에서 뺀다. `7.2.2-1 H:`처럼 번호 뒤에 공백과 글자 하나가 붙은 캡션은 색인하지 않는다.
- 같은 번호가 둘 이상이면 그 번호는 모호하다. 후보마다 앵커를 달고, 한 파일에 같은 번호가 또 나오면 두 번째부터 `~2`, `~3`을 붙인다(`table-8.13.2.1.1-2~2`). 모호한 번호는 같은 규격 안에서 참조와 같은 파일·같은 하위 제목 아래의 후보가 하나뿐일 때만 그 후보로 해석한다.
- 제목·캡션이 Void뿐인 번호(`Table 5.5-2: Void`, `## 7.4A.3 Void`, 본문 없는 `Void` 조항)는 `void`다.

**링크.** `resolved`와, 위치(Void 제목·캡션 줄)가 있는 `void` 참조를 링크한다. 본문 없는 Void 조항은 링크하지 않는다. 번호가 정확히 같은 대상이 없으면 대소문자만 다른 번호가 하나뿐일 때 그것으로 해석한다(`5.3.19a` → `5.3.19A`). 본문 없는 조항은 첫 하위 조항 파일로, 하위 조항이 없으면 바로 뒤의 글자 접미 조항(`4.3.2` → `4.3.2a`) 파일로 링크한다. 본문은 `[clause 5.1.2](상대경로.md#anchor)`, HTML 표 안은 `<a href="상대경로.md#anchor">clause 5.1.2</a>`. 상대 경로는 항상 `/` 구분이며 다른 규격은 `../../{code}/clauses/{file}.md`다. 링크 텍스트는 원문 글자 그대로다(`clause`·`Table` 같은 단어와 번호). 코드 펜스, 수식, HTML 태그, 제목·캡션 줄 안의 참조는 링크하지 않는다.

**media.** 본문의 `](../media/`와 `src="../media/`는 `raw/{code}/media/`를 가리키도록 `linked/{code}/clauses`에서 본 상대 경로로 바꾼다.

**refs.json.** `{"spec", "version", "refs": [...]}`. 항목: `from_file`, `from_clause`, `line`, `text`, `kind`(`table`/`figure`/`clause`), `target_spec`(규격 번호), `target_id`, `target_file`, `anchor`, `status`. `status`는 `resolved`, `missing_target`(규격은 있으나 번호가 없음), `missing_spec`(규격이 코퍼스에 없음), `ambiguous`(번호가 둘 이상), `void`(대상이 Void) 중 하나다. 사용자 지정 대상으로 해석한 항목에는 `"override": true`가 붙는다. 파일·줄·위치 순으로 정렬한다.

**사용자 지정 대상(`--overrides`).** `{"overrides": [{"spec", "file", "line", "text", "target_spec", "target_id"[, "target_file", "target_anchor"]}]}`. `spec`(규격 코드)·`file`·`line`(raw 줄)·`text`가 같은 참조를 `target_spec`의 `target_id`(참조와 같은 종류)로 해석해 `resolved`로 링크한다. 대상 번호가 모호하면 `target_file`(과 `target_anchor`)로 후보를 고른다. 참조나 대상을 찾지 못한 항목은 적용하지 않고 경고로 알린다. 링크 텍스트는 원문 그대로이므로, 번호를 바로잡은 지정은 텍스트 번호와 앵커 번호가 다를 수 있다(검사기는 `override` 항목에만 이를 허용한다). 파일이 없으면 지정이 없는 것으로 본다. 점검 HTML(`mk_unresolved.py`)이 이 파일을 만든다.

**index.json.** 규격 코드마다 `spec_number`, `version`, `release`와 `clauses`·`tables`·`figures`(번호 → `{file, anchor}` 또는 `{ambiguous: true, candidates: [{file, anchor}, …]}`). 같은 규격 번호의 여러 버전이 있으면 가장 높은 버전의 코드를 대상으로 삼는다.

**역참조 절.** 다른 파일에서 해석되어 이 파일을 가리키는 링크가 있으면 파일 끝에 붙는다(같은 파일 안 참조는 제외). 출처 규격 코드와 파일 경로, 대상 앵커, 참조 텍스트가 모두 같은 항목은 한 번만 기록한다.

```
(raw 본문)

<!-- spec2md:backlinks -->
## Referenced by

- [TS 38.213 10.1](../../38213-j50/clauses/0001_10.1_x.md) — clause 5.1.2
```

**줄바꿈 규칙.** raw 조항 파일은 정확히 LF 하나로 끝난다. 역참조 절은 본문의 마지막 LF 뒤에 빈 줄 하나를 두고 `<!-- spec2md:backlinks -->` 마커 줄로 시작한다. 문자열로 쓰면 다음과 같다.

```
raw 끝:     "...본문\n"
linked 끝:  "...본문\n\n<!-- spec2md:backlinks -->\n## Referenced by\n\n- ...\n"
```

되돌릴 때는 `"\n\n<!-- spec2md:backlinks -->"`가 처음 나오는 곳부터 끝까지 잘라내고 LF 하나를 다시 붙인다. 그러면 raw 끝으로 돌아온다. 나머지 변경(앵커 줄, 링크, media 접두사)도 모두 기계적으로 되돌릴 수 있어야 하며, 되돌린 결과가 raw와 바이트 단위로 같지 않으면 ERROR다. 모든 출력은 UTF-8, LF, BOM 없음이다. 경로에는 역슬래시가 없다(위의 이스케이프 표기는 설명용이며 파일에 들어가지 않는다).
