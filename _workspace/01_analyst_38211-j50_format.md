# 형식 분석: 38211-j50.docx (TS 38.211 V19.5.0)

- 분석 대상: `specs/38211-j50.docx` (원본은 읽기만 했다)
- 구조 JSON: `_workspace/01_inspect_38211-j50.json` (`inspect_docx.py --json` 출력, 수정 없음)
- 표기: **[확인]**은 XML을 직접 세어 얻은 값, **[추정]**은 근사 모델로 계산한 값이나 해석이다.

### 스크립트 실행 메모
- `inspect_docx.py ... --json ... --samples 3`을 실행했더니 JSON은 정상으로 기록됐다. 그런데 요약 출력 도중 `UnicodeEncodeError: 'cp949' codec can't encode character '–'`로 종료됐다(Windows 콘솔 기본 인코딩 문제). `PYTHONIOENCODING=utf-8`로 다시 실행하면 정상 출력된다. 스크립트에 `sys.stdout.reconfigure(encoding="utf-8")`를 넣으면 이 문제가 없어진다.
- 수식, OLE, 표, 크기 세부 조사는 스크래치 스크립트(stdlib, `ElementTree`)로 했다. 프로젝트 파일은 바꾸지 않았다.

---

## 1. 파일 기본 정보

| 항목 | 값 |
| --- | --- |
| 규격 | 3GPP TS 38.211 "NR; Physical channels and modulation" |
| 버전 | 표지 `ZA` = `3GPP TS 38.211 V19.5.0 (2026-09)`, `ZT` = `(Release 19)`. 파일 이름 `j50`(19.5.0)과 일치한다 [확인] |
| 메타데이터 | `docProps/core.xml` subject에 "(Release 15)"가 남아 있다. 오래된 값이므로 쓰지 말 것 [확인] |
| 파일 크기 | 1,670,145 B (docx), `word/document.xml` 17,950,975 B |
| 패키지 | `word/media`: wmf 571, emf 3, png 1 / `word/embeddings`: OLE `.bin` 739, `.vsd` 2 [확인] |
| 본문 최상위 자식 | `w:p` 2,513, `w:tbl` 132, `w:bookmarkStart` 4, `w:bookmarkEnd` 26, `w:sectPr` 1. `w:sdt`와 `mc:AlternateContent`는 0 [확인] |
| 제목 수 | 275개. L1 10 (`heading 1` 9 + Annex `heading 8` 1), L2 25, L3 55, L4 87, L5 81, L6 17 (`heading 6` 15 + `H6` 2) [확인] |
| 최대 제목 레벨 | 6. 레벨이 건너뛰는 곳 없음, 텍스트가 빈 제목 없음 [확인] |
| 부속서 | Annex A (informative) "Change history" 하나. 제목 안에 `w:br`가 있다 [확인] |
| 변경 추적 | `w:ins` 0, `w:del` 0, moveFrom/To 0, 주석 0, 각주 0, 텍스트 상자 0 [확인] |
| ASN.1 / PL | ASN1START/STOP 0/0, `PL` 스타일 0. 코드 블록이 없는 규격이다 [확인] |
| 필드 | TOC 1, PAGEREF 273 (목차용), QUOTE 1. 하이퍼링크 0 [확인] |

---

## 2. 스타일 빈도와 해석

본문(첫 제목 Foreword 이후)과 표 셀을 나눠 셌다 [확인].

| 스타일 | 전체 | 본문 | 표 셀 | 해석 / 일반 표와 다른 점 |
| --- | ---: | ---: | ---: | --- |
| TAC | 13,854 | 0 | 13,854 | 표 셀(가운데 정렬) |
| Normal | 3,007 | 789 | 2,211 | 표지 7. **표 셀 안 Normal 2,211**: 행렬 표 등에서 셀이 TAx가 아닌 Normal을 쓴다 |
| TAR | 2,123 | 0 | 2,123 | 표 셀(오른쪽) |
| TAL | 1,261 | 0 | 1,261 | 표 셀(왼쪽) |
| B1 | 522 | 522 | 0 | 목록. 276개 문단에 인라인 OMML이 있다 |
| TAH | 357 | 0 | 357 | 표 머리글. 82개 문단에 oMathPara가 있다 |
| EQ | 230 | 230 | 0 | 수식 문단. 구조는 4절 참고 |
| TH | 132 | 132 | 0 | 표 제목. **101개(77%)에 수식이 있다**(OMML 인라인 79, OLE 14, 혼합 6, OLE만 2). Visio 그림 문단 2개도 TH를 쓴다 |
| B2 / B3 | 121 / 19 | | | 목록 레벨 2, 3 |
| EW | 92 | 92 | 0 | 3.2 Symbols 목록. **60개(65%)는 용어 자리가 수식이다**(OMML 38, OLE 16, 혼합 6) |
| EX | 18 | 18 | 0 | 2 References 목록(`[1]\t3GPP TR 21.905…`) |
| FP | 20 | 0 | – | 표지에만 있다(Keywords 등). 건너뛴다 |
| TF | 2 | 2 | 0 | 그림 제목. 실제 그림은 2개뿐이다 |
| H6 | 2 | 2 | 0 | 번호 있는 6수준 조항(6.4.1.1.1.1, 6.4.1.1.1.2). 다른 6수준 조항은 `heading 6` 15개를 쓴다 |
| NO | 1 | 1 | 0 | NOTE |
| heading 1~6, 8 | 275 | | | 2절 개요 참고 |
| toc 1~6, 8 | 273 | | | 목차. 건너뛴다. toc 5/6 안에 OMML 8개 |
| ZA/ZB/ZT/ZU/ZV/TT | 12 | | | 표지와 목차 제목. 건너뛴다 |

- 정의는 있으나 쓰이지 않는 스타일: `Heading 1 unnumbered`, `heading3`(styleId heading30), `heading4`(heading40). `heading3`/`heading4` 이름은 `HEADING_RE`(`^(?:heading\s*|h)(\d)$`)에 맞는다. 다른 버전에서 쓰이면 제목으로 잡히므로 주의한다 [확인: 사용 0회].
- `Editor's Note`, `CR*` 계열 스타일은 없다 [확인].

---

## 3. 변환 위험 요소 (수치)

### 3.1 수식 개요

| 수식 형태 | 개수 | 비고 |
| --- | ---: | --- |
| OMML `m:oMath` | **2,910** (TOC 안 8 포함, 본문 2,902) | `inspect_docx.py`의 `equations` 값. 중첩 oMath 0 |
| OMML `m:oMathPara` | **919** | 이 안의 oMath 1,008개. 나머지 1,902개는 문단에 바로 들어 있다 |
| OLE `Equation.3` (MS Equation 3.0) | **686** | 미리보기 WMF. `Equation Native` 스트림이 있고 MTEF 버전 3 |
| OLE `Equation.DSMT4` (MathType) | **52** | 미리보기 WMF. MTEF 버전 5 |
| MathType 그림(`w:drawing` WMF) | **213회 / 서로 다른 파일 65개** | OLE가 아닌 일반 그림으로 붙은 수식. 18개 파일에만 MTEF가 들어 있다 |
| 그 밖의 OLE | Visio.Drawing.11 2, Word.Picture.8 1 | 실제 그림 2, 표지 로고 1 |

- **"그림" 수가 과대 계산된다.** `inspect_docx.py`의 `figures`는 drawing 214 + ole_object 741 = 955다. 그런데 실제 그림(TF 캡션 대상)은 Visio 2개뿐이고, 표지 로고 2개(png 1, Word.Picture.8 EMF 1)를 빼면 나머지 951개는 수식이다 [확인]. 그대로 두면 `check_output.py`의 `figures` 경고(소스 955 대비 90%)가 늘 거짓으로 뜬다.
- 213개 drawing은 높이 중앙값 14.25pt이고 202개가 20pt 이하다. WMF 64/65개에 "MathType" 문자열이 있다. 그래서 인라인 수식 그림이라고 판단했다 [확인: 높이와 문자열, 추정: 용도].
- 표 제목 TH 2개에도 수식 그림(`image400.wmf`)이 있다(DM-RS 표 제목).

### 3.2 인라인 수식과 단독(display) 수식 구분

수식이 있는 문단은 2,423개다(OMML, OLE, MathType 그림 중 하나 이상). 문단 안에 수식 밖 텍스트(공백, 마침표, 괄호, 쉼표 제외)가 있으면 "inline"으로 분류했다 [확인].

| 분류 | 본문 | 표 셀 |
| --- | ---: | ---: |
| `m:oMathPara` 포함(단독) | 151 | **768** |
| oMath만, 주변 텍스트 없음(사실상 단독) | 44 | 18 |
| oMath 인라인(텍스트 사이) | 748 | 93 |
| OLE만(단독) | 62 | 276 |
| OLE 인라인 | 114 | 55 |
| oMath 인라인 + OLE 인라인 혼합 | 90 | 2 |
| oMath만 + OLE만 | 0 | 2 |

- oMathPara가 있는 문단 919개 중 912개는 수식 밖 텍스트가 없다. 7개는 텍스트와 함께 있다(`(ordered from left to right in` 6, `and` 1). 이 텍스트를 버리면 안 된다 [확인].
- oMathPara 안의 oMath 수: 1개 881, 2개 15, 3개 7, 4개 9, 5개 2, 6개 5. 한 oMathPara에 oMath가 여럿이면 줄마다 하나씩이다 [확인].
- `oMathParaPr/jc`: 미지정 914, left 2, center 3 [확인].
- **단독 수식 768개가 표 셀 안에 있다**(프리코딩 행렬 표 등). 셀 스타일 분포는 Normal 819, TAC 273, TAH 175, TAR 35, TAL 20 (OMML+OLE 개수 기준) [확인].
- 제목 8개에 OMML이 있다(4.5절 참고).

### 3.3 EQ 스타일 문단 구조

- `EQ` 스타일 정의: `basedOn Normal`, 탭 정지 `center 4536`, `right 9072`, `keepLines`, `noProof`. 직접 탭을 지정한 문단은 230개 중 1개뿐이다 [확인].
- 문단 자식 순서 패턴(연속된 같은 요소는 하나로 묶음, 북마크 제외) [확인]:

| 패턴 | 개수 | 해석 |
| --- | ---: | --- |
| `oMathPara` | 126 | 최신 방식. 탭 없음 |
| `OLE` | 44 | Equation.3/DSMT4 단독 |
| `TAB oMath` | 36 | 구 방식(가운데 탭 + 인라인 oMath). display로 처리해야 한다 |
| `TAB OLE` | 12 | 탭 + OLE |
| `OLE TXT` | 3 | TXT는 `.`(문장 끝 마침표) |
| `TAB oMath oMathPara` | 1 | |
| `TAB oMath TAB oMath` | 1 | 한 줄에 수식 두 개 |
| 수식 그림(drawing)만 | 6 | MathType WMF |
| 텍스트 `.`만 | 1 | |

- **수식 번호가 없다.** `(n)`이나 `(5.x-y)` 형식으로 끝나는 수식 문단이 0개이고, 오른쪽 탭(9072) 뒤 번호 텍스트도 없다 [확인]. 그러므로 "탭 + 수식 + 번호" 분리 로직은 38.211에서는 쓰이지 않는다. 탭은 버리면 된다.

### 3.4 OMML 요소 빈도 (최상위 oMath 2,910개 기준, LaTeX 변환 대상)

구조 요소 [확인]:

| 요소 | 개수 | 속성·값 분포 | LaTeX 대응(제안) |
| --- | ---: | --- | --- |
| `m:r` / `m:t` | 22,384 / 22,270 | m:t 글자 합 40,379, 수식당 중앙값 7자, p90 35, 최대 510 | 본문 |
| `m:sSub` | 1,904 | | `{e}_{sub}` |
| `m:d` | 1,871 | 기본 `( )` 960, `[ ]` 578, `{ }` 187, `{`+빈 끝 35, `⌊⌋` 95, `⌈⌉` 15, 빈 끝 `endChr=''` 36, 빈 시작 1. 여러 `m:e`(sepChr) 0 | `\left( … \right)`, 빈 문자는 `.` |
| `m:sSubSup` | 1,155 | | `{e}_{sub}^{sup}` |
| `m:mc`/`m:mcs`/`m:mcPr` | 651/635/651 | 열 속성(count, mcJc) | 무시 가능 |
| `m:m` (행렬) | 635 | `m:mr` 2,764. 최대 8행 x 8열. 감싼 구분자: `[ ]` 564, `{`+빈 끝 35(조건식), 단독 36 | `bmatrix`, `cases`, `matrix` |
| `m:f` | 572 | `type=lin`(선형 a/b) 148, 나머지 막대 분수 | `\frac{}{}` / `a/b` |
| `m:acc` | 413 | chr U+0305(윗줄) 268, U+0303(물결) 145 | `\bar{}`, `\tilde{}` |
| `m:sSup` | 334 | | `{e}^{sup}` |
| `m:rad` | 246 | 모두 `degHide=1` | `\sqrt{}` |
| `m:nary` | 26 | chr ∑ 25, ∏ 1. limLoc undOvr 13, subSup 13. chr 생략(∫) 0 | `\sum_{}^{}`, `\prod` |
| `m:func` | 1 | | `\operatorname` |
| `m:limLow` | 1 | | `\underset{}{}` |
| `m:eqArr`, `m:groupChr`, `m:bar`, `m:box`, `m:borderBox`, `m:sPre`, `m:limUpp`, `m:phant` | **0** | | 구현 우선순위 낮음 |

런 속성 [확인]:

| 속성 | 개수 | 대응 |
| --- | ---: | --- |
| `m:sty=p` (직립) | 3,429 | 두 글자 이상이면 `\mathrm{}`(mod, min 등이 `func`가 아닌 직립 런으로 들어 있다) |
| `m:nor` (일반 텍스트) | 2,856 | `\text{}`. 아래첨자 `RB`, `PUCCH`, `if`, `otherwise` 등 |
| `m:sty=bi` / `m:sty=b` | 496 / 185 | `\boldsymbol{}` / `\mathbf{}` |
| `m:aln` (정렬점) | 123 | `aligned` 환경의 `&` |
| `w:br` (m:r 안 줄바꿈) | 114 | `\\`. 행렬이 아닌 수식 104개가 여러 줄이다 → `\begin{aligned}…\end{aligned}` |
| `m:scr=script` | 6 | `\mathcal{}` |
| `w:rFonts` Cambria Math | 21,262 | 무시 |

- 중첩 깊이: 최대 23, 평균 5.9 (XML 요소 깊이) [확인].
- m:t의 비ASCII 문자(빈도순): μ 362, × 289, … 240, ∈ 167, Δ 72, ∙ 54, δ 48, β 39, λ 37, α 35, ≤ 23, υ 22, π 21, ρ 19, ⋅ 18, ⋮ 12, κ 11, φ 11, ≥ 10, ∆(U+2206) 10, ν 5, ⋯ 3, γ 2, ε 1, ≠ 1, ϵ 1. 모두 LaTeX 명령으로 매핑할 수 있다 [확인].
- m:t 안 ASCII `<` 29회, `>` 10회, `|` 0, `&` 0 [확인]. HTML 표 안에 넣을 때는 `<`를 `\lt`나 `&lt;`로 바꿔야 HTML 파서가 태그로 오인하지 않는다.
- **시험 변환 결과**: 위 매핑만으로 만든 stdlib 시제품(약 150줄)으로 2,910개를 모두 변환했다. 모르는 요소 0, 매핑 안 된 문자 0. LaTeX 길이는 합계 178,334자, 중앙값 32자, p90 166자, 최대 2,038자(조건식 행렬)였다 [확인: 시제품 기준, 렌더링 검증은 안 함]. 예시:
  - `\tilde{b}\left( i \right)=\left( b\left( i \right)+c(i+v{M}_{\text{bit}}) \right) \text{mod} 2`
  - `{k}_{\text{TC}}^{\left( {p}_{i} \right)}=\left\{ \begin{matrix}… & \text{if}… \\ … \end{matrix} \right.` (→ `cases`로 바꾸는 것이 좋다)

### 3.5 OLE 수식(Equation.3 / DSMT4) 상세

- 위치 [확인]:
  - 본문 401개: Normal 215, B1 56, EQ 59, TH 28, EW 26, B2 17
  - 표 셀 337개: TAC 183, TAH 74, Normal 33, TAR 27, TAL 20
- 모두 `Type=Embed`, `DrawAspect=Content`이고 미리보기는 `v:imagedata` → WMF다. OLE 738개가 미리보기 파일 510개를 참조한다(69개 파일은 여러 번 쓰인다) [확인].
- 738개 `.bin` 모두 CFB 컨테이너이고 `Equation Native` 스트림이 있다. 헤더 뒤 MTEF 버전 바이트: Equation.3 → 3 (686), DSMT4 → 5 (52) [확인].
- 미리보기 WMF 507개 중 45개에만 MTEF가 들어 있다(`AppsMFC`) [확인].
- 문단 텍스트만 뽑으면 그 자리가 빈 문자열이 된다. 예: B1 `-  and  are given by clause 4.2 …`, EW `Resource element with frequency-domain index  and time-domain index  …`. 텍스트만 남기면 의미가 깨진다 [확인].
- 선택지 [추정, 결정 필요]:
  1. 1차: `media/`에 WMF를 추출하고 그 자리에 `![equation](../media/imageN.wmf)`를 둔다. manifest에는 `equations`와 따로 미변환 개수를 기록한다. WMF는 대부분의 Markdown 뷰어와 LLM이 읽지 못하므로 위키 raw로는 정보 손실이다.
  2. 2차: MTEF v3/v5 파서로 LaTeX를 만든다. stdlib에는 CFB 리더가 없다(`olefile`, `lxml`, `python-docx` 모두 미설치 확인). `Equation Native`가 4,096B 미만이면 mini-stream(64B 섹터)에 있어 비연속일 수 있다. 그래서 바이트 검색만으로는 스트림 전체를 안전하게 읽을 수 없고, 최소한의 CFB 리더를 구현해야 한다.

### 3.6 표

| 항목 | 값 [확인] |
| --- | --- |
| 본문 표 | 132 (중첩 표 0) |
| 병합 셀이 있는 표 | **80 (61%)**. gridSpan 79, vMerge 29 |
| 병합이 첫 두 행(머리글)에만 있는 표 | 80개 중 **63개**. `w:tblHeader` 지정은 없다 |
| 여러 문단 셀이 있는 표 | 10 |
| GFM 파이프 표 가능(병합 없음, 셀당 한 문단) | 49 (37%) |
| OMML 포함 표 / OLE 포함 표 / 그림(수식 그림) 포함 표 | 101 / 37 / 15 |
| 최대 행 / 최대 열 / 전체 행 | 265 / 25 / 2,268 |
| 100행 이상 표 | 4 (PRACH 설정표 3개: 258, 265, 258행 / Annex A 변경 이력 185행) |

- 표 셀 수식이 많다. 셀 안 display 수식(oMathPara)은 `$$`가 아닌 인라인 `$…$`로 써야 HTML 셀이나 파이프 셀에서 깨지지 않는다 [추정].
- 행렬 수식의 `&`와 `\\`가 HTML 셀 안에 들어간다. `&` 뒤에 공백이 오면 HTML 엔티티로 해석되지 않지만, 검사기 관점에서는 원문 보존 규칙을 정해야 한다.

### 3.7 그 밖의 위험 요소

- **조항 번호에 문자 접미사가 있다**: `6.3.1.2a Inter-slot cover code`(L4), `6.3.2.5.2A Spreading`(L5). 지금의 `CLAUSE_RE`는 이 둘을 `clause=None`(번호 없는 제목)으로 파싱한다 [확인]. 검사 키가 slug(`6-3-1-2a-inter-slot-cover-code`)가 되므로, 변환기가 번호를 올바르게 파싱하면 missing/extra 불일치가 생긴다.
- **Void 조항**: `6.4.1.1.2 (void)` 1개(L5) [확인].
- **수식이 든 제목 8개**: `7.4.4.1.1`, `7.4.4.1.2`, `7.4.5.1.1`~`7.4.5.1.3`(L5, 제목 `Generation of <수식>`), `7.4.1.6.4.2`~`7.4.1.6.4.4`(L6, `… mapping from <수식> to …`). `para_text`가 `m:t`를 읽지 않으므로 JSON 개요의 제목은 `Generation of`(5개 중복)이 되고, L6 3개는 수식 자리에 공백 두 개가 남는다 [확인]. 원래 표기는 `rZC,m(n)`, `rWUS(n)`, `rOOK(n)`, `rZC(n)`, `rLPSS(n)`, `it`, `if`, `is`(아래첨자)다.
- 제목 `5.1.1 π/2-BPSK`의 π는 일반 텍스트 U+03C0이다(OMML이나 w:sym이 아님). cp949 콘솔에서만 깨져 보인다 [확인].
- `w:sym` 0, PUA 문자 0, Symbol 글꼴 텍스트 런 0 [확인]. 기호 변환 문제는 없다.
- 본문 `w:br` 173개 중 114개는 OMML 안(수식 줄바꿈)이고 59개는 텍스트 런 안이다 [확인].
- 최상위 `w:bookmarkStart`/`End`가 본문 자식으로 30개 있다. `p`/`tbl`이 아닌 자식은 무시하면 된다 [확인].

---

## 4. 권장 `--split-depth`와 크기 분포

### 4.1 추정 방법 [추정]
- 블록별 Markdown 길이를 근사했다.
  - 문단: w:t 글자 수 + 2
  - OMML: m:t 글자 수 + 구조 요소별 LaTeX 부가 길이(분수 9, 아래·위첨자 3~6, 행렬 30+행당 4, `\mathrm`/`\text` 7~9, 비ASCII 문자 +4)
  - OLE·그림: 40~45자(링크)
  - 표: 병합 표는 HTML(셀당 9, 행당 10), 나머지는 파이프(셀당 3)
- 보정: OMML 근사 합 170,552자, 시제품 LaTeX 합 178,334자(오차 약 -4%). 전체 추정 본문은 약 **662,600자**이고, 그중 표가 약 356,800자다(표 안 순수 텍스트는 59,583자뿐이고 대부분 HTML 마크업이다).
- 본문이 거의 없는(200자 이하) 제목은 `file: null` 후보로 따로 셌다.
- `--max-chars 60000`은 SKILL 설명대로 "초과하고 더 깊은 제목이 있으면 그 파일만 한 단계 더 분할"로 모의했다.

### 4.2 분할 깊이별 결과 (`--max-chars 60000` 적용) [추정]

| depth | 항목 수 | 본문 파일(>200자) | null 후보 | 중앙값 | p90 | 최대 | <2k | 2k–10k | 10k–30k | 30k–60k | >60k | 자동 추가 분할 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 2 | 44 | 33 | 11 | 4.4k | 74k | 143k | 12 | 9 | 7 | 1 | 4 | 6.3, 6.4, 7.4 |
| **3** | **111** | **81** | **30** | **1.7k** | **23.8k** | **94k** | 43 | 22 | 11 | 3 | **2** | 6.3.1, 6.3.3, 6.4.1, 7.4.1 → L4 |
| 4 | 177 | 122 | 55 | 1.2k | 10.0k | 94k | 76 | 33 | 8 | 3 | 2 | 없음 |
| 5 | 258 | 165 | 93 | 1.1k | 7.5k | 94k | 116 | 38 | 8 | 1 | 2 | 없음 |

max-chars 없이 depth 3만 쓰면 60k를 넘는 파일이 4개다: 6.3.3 PRACH 142.9k, 6.3.1 PUSCH 101.7k, 6.4.1 UL RS 91.1k, 7.4.1 DL RS 74.4k.

### 4.3 권장: `--split-depth 3` + `--max-chars 60000`
- depth 3에서는 큰 하위 트리 4개만 L4로 자동 분할된다. 나머지는 L3 단위라 파일 수가 적당하고(본문 파일 81), p90이 23.8k다.
- depth 4는 null 후보가 55개로 늘고 중앙값 1.2k의 작은 파일이 많아진다. 그런데도 60k 초과 2개는 그대로 남는다.
- **어떤 depth로도 60k 아래로 내려가지 않는 단말 조항이 2개 있다**(하위 제목 없음):
  - `6.3.3.2 Mapping to physical resources`(PRACH): 약 94k. 원인은 258~265행 설정표 3개(각 2,300여 셀)의 HTML 마크업이다. 셋 다 병합이 0~1행(머리글)에만 있다.
  - `6.3.1.5 Precoding`(PUSCH): 약 91k. 원인은 프리코딩 행렬 표 50개(대부분 병합, 셀 안 `m:m` 행렬)다.
  - 다음 크기 조항: 6.3.3.1 48.9k, Annex A 29.6k(185행 이력 표 하나), 6.4.1.1.3 24.9k.
- 머리글에만 병합이 있는 표(63개)를 파이프 표로 평탄화하면 6.3.3.2는 약 35~40k로 줄어든다고 추정한다. 6.3.1.5는 표 단위 분할 같은 별도 규칙이 없으면 60k를 넘는다.

---

## 5. 출력 규약(output-contract.md) 보완 제안

규약을 바꾸면 변환기, `check_output.py`, `topic-grouping`을 함께 고쳐야 한다.

1. **수식 출력 규칙을 구체화한다** (5절 "수식 (OMML)" 행).
   - display 판정: `m:oMathPara`가 있는 문단, `EQ` 스타일 문단, 수식 밖 텍스트가 없는 문단(공백·마침표·쉼표만 허용) → `$$…$$` 블록. 그 밖은 인라인 `$…$`.
   - 표 셀과 목록(B1 안 oMathPara 3개) 안의 display 수식은 인라인 `$…$`로 쓴다(필요하면 `\displaystyle`).
   - oMathPara 안의 oMath가 여러 개면 줄마다 하나씩 쓰거나 `gathered`로 묶는다. `w:br`/`m:aln`이 있는 수식은 `aligned`로 쓴다.
   - `m:d{ … }` + 끝 문자 없음 + 단일 `m:m` → `cases`, `[ ]` + `m:m` → `bmatrix`.
   - EQ의 탭은 버린다. 38.211에는 수식 번호가 없으므로 번호 처리 규칙은 "있으면 `\tag{}`"처럼 선택 사항으로 둔다.
   - HTML 표 안의 LaTeX는 `<`, `>`를 이스케이프한다. 파이프 표 안에서는 `|`를 `\vert`로 쓴다.
2. **OLE 수식(Equation.3/DSMT4)과 MathType 그림을 위한 규칙을 추가한다.** 지금 규약의 "OLE 개체 → 미리보기 이미지"를 그대로 적용하면 수식 951개가 그림으로 집계된다. 제안:
   - 수식 OLE와 MathType WMF 그림은 "수식"으로 분류한다.
   - 출력은 `![equation](../media/imageN.wmf)`(1차)로 하고, 이후 MTEF→LaTeX 변환을 선택 기능으로 둔다.
   - manifest에 `equations`(전체)와 함께 `equations_unconverted`(이미지나 자리표시자로 남은 수)를 기록한다.
3. **`inspect_docx.py` JSON의 수식·그림 집계를 나눈다.** 예: `equations_detail: {omml, omml_para, ole_equation, mathtype_picture}`. `figures`에서는 수식 OLE와 수식 그림을 뺀다. `check_output.py`는 그림 수 비교를 실제 그림 기준으로 하고, 지금 하지 않는 수식 수 비교를 추가한다. 지금 상태로는 그림 경고가 항상 거짓으로 뜬다.
4. **`CLAUSE_RE`에 문자 접미사를 허용한다.** 예: `^\s*((?:[A-Z]|\d+[A-Za-z]?)(?:\.\d+[A-Za-z]?)*)[\s\t]+(.+)$`. 이 규격 275개 제목에 시험해 보니 바뀌는 것은 `6.3.1.2a`, `6.3.2.5.2A` 두 개뿐이었다(나머지 결과 동일) [확인]. 기준 구현(`inspect_docx.py`)과 변환기를 함께 바꿔야 한다.
5. **제목 안 수식 처리를 정한다.** `para_text`/제목 추출에서 `m:t`를 이어 붙여 평문 제목을 만들 것을 제안한다(`Generation of rZC,m(n)`). front matter `title`과 slug는 한 줄 평문으로 쓰고, 파일 첫 줄 `#` 제목에만 LaTeX를 쓸지 정한다. `inspect_docx.py`도 같은 방식으로 바꿔야 제목 대조가 맞는다.
6. **`--max-chars` 자동 분할을 manifest와 검사기에 반영한다.** 지금 `check_output.py`는 `level <= split_depth` 제목만 기대값으로 본다. 그래서 depth 3에서 자동 분할로 생긴 L4 항목(이 규격에서 약 21개)이 "manifest clauses not found in source outline" 경고로 뜬다. manifest에 `"auto_split": ["6.3.1", "6.3.3", "6.4.1", "7.4.1"]`나 항목별 `"auto_split": true`를 두고, 검사기가 이를 기대값에 넣도록 할 것을 제안한다.
7. **제목으로 나눌 수 없는 큰 단말 조항을 어떻게 다룰지 정한다**(6.3.3.2, 6.3.1.5). 선택지:
   - (a) 경고만 하고 허용한다.
   - (b) 병합이 머리글 행에만 있는 표를 파이프 표로 평탄화한다(병합 셀 내용은 반복하거나 머리글을 합친다).
   - (c) TH 캡션 단위로 파일을 나눈다(규약 2절의 파일 이름 규칙 확장 필요).
8. **EW에서 용어가 수식인 경우의 형식**(60/92): `- **$N_{\text{sc}}^{\text{RB}}$**: …`는 bold와 수식이 겹친다. `- $N_{\text{sc}}^{\text{RB}}$: …`를 제안한다.
9. **Void 조항**: `(void)` 제목은 manifest에 넣고 `file: null`로 둔다. 현재 규약으로도 처리되지만 Void 판정 기준(`(void)`, `Void`, 대소문자)을 명시할 것을 제안한다.

---

## 리더에게 주는 요약
1. 수식은 OMML 2,910개(oMathPara 919개, 그중 표 셀 안 768개)와 OLE 738개(Equation.3 686개(MTEF v3), DSMT4 52개(MTEF v5)), MathType WMF 그림 213개(서로 다른 파일 65개)로 섞여 있다. 수식 번호는 0개다.
2. OMML은 sSub 1,904, d 1,871, sSubSup 1,155, m 635, f 572, acc 413, sSup 334, rad 246, nary 26으로 요소가 제한적이고 eqArr는 0이다. stdlib 시제품이 2,910개를 모르는 요소 없이 LaTeX로 바꿨다.
3. OLE·그림 수식 951개가 지금 "그림"으로 집계된다(실제 그림은 Visio 2개). 검사기 그림 경고가 거짓으로 뜨고, 텍스트만 뽑으면 해당 수식 내용이 사라진다. 수식/그림 분류와 OLE 처리 방침을 규약에 넣어야 한다.
4. `CLAUSE_RE`가 `6.3.1.2a`와 `6.3.2.5.2A`를 번호 없는 제목으로 파싱한다. 제목 8개에는 수식이 있어 제목이 잘린다. 병합 표는 80/132(61%)이고, 그중 63개는 머리글 행에만 병합이 있다.
5. 권장 설정은 `--split-depth 3 --max-chars 60000`이다(본문 파일 81개, 중앙값 1.7k, p90 23.8k). 단, 하위 제목이 없는 6.3.3.2(약 94k)와 6.3.1.5(약 91k)는 어떤 depth로도 60k 아래로 내려가지 않는다.
