# spec2md

## 하네스: 3GPP 규격 → Markdown raw 변환

**목표:** 로컬 3GPP 규격 .docx를 LLM 위키 생성 전 단계의 조항·주제별 Markdown raw 파일(영어)로 충실하게 변환한다.

**호출 조건:** 3GPP 규격 변환, 변환 도구(spec2md) 개발·수정, 변환 결과 검사, 주제별 묶음, 재변환 관련 작업을 요청받으면 `spec2md-orchestrator` 스킬을 사용한다. 단순 질문에는 직접 답해도 된다.

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
| --- | --- | --- | --- |
| 2026-11-25 | Harness v2로 처음 구성 | 전체 | - |
| 2026-11-25 | 분할 규격(`_cover`, `_s00-07` …) 병합 규칙, 제목 해석 규칙(문자 접미 번호·번호 깊이 level·H6·오타 보정), 본문 규칙 보완(TH/TF, 파이프 표 조건, 첨자, OLE 수식 LaTeX 복원) | output-contract.md, inspect_docx.py, check_output.py, check_all.py | 첫 일괄 변환(38개 규격) 형식 분석·검사 결과 |
