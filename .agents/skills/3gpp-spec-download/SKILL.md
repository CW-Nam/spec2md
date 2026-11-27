---
name: 3gpp-spec-download
description: 3GPP 공식 Specs/latest에서 선택한 Release의 TS/TR Word 원본을 다운로드한다. 기존 규격 목록 재다운로드, 목록 저장·불러오기, 다른 Release의 최신 버전 받기에 사용한다.
---

# 3GPP 규격 다운로드

기본 목록은 [specs.txt](specs.txt)다. 저장소의 `3gpp-specs/`에 있던 문서에서 뽑은 규격 번호 44개가 들어 있다. 기본 Release는 `Rel-19`이며, 기본 저장 위치는 사용자 홈의 `~/3gpp-specs/`다.

[다운로드 스크립트](scripts/download_specs.py)는 [3GPP 공식 디렉터리](https://www.3gpp.org/ftp/Specs/latest/)의 `Rel-N/XX_series/`에서 규격 번호별 최신 ZIP을 찾아 Word 문서를 푼다. 분할된 문서도 모두 저장하며, 같은 이름의 기존 파일은 건너뛴다. `--dry-run`은 공식 디렉터리에서 대상 ZIP URL을 확인한다. 결과를 전달할 때는 다운로드, 건너뜀, 해당 Release에서 찾지 못한 규격, 실패를 확인한다.

저장소 루트에서 아래 명령을 실행한다. 다른 작업 디렉터리에서는 스크립트의 절대 경로를 사용한다.

```powershell
uv run --no-project python .agents/skills/3gpp-spec-download/scripts/download_specs.py download
uv run --no-project python .agents/skills/3gpp-spec-download/scripts/download_specs.py download --release Rel-18 --list my-specs.txt
uv run --no-project python .agents/skills/3gpp-spec-download/scripts/download_specs.py save-list --source ./3gpp-specs --list my-specs.txt
```

`save-list`는 지정한 폴더의 DOCX, DOC 또는 ZIP 파일명에서 규격 번호를 뽑아 중복을 제거한 뒤 지정한 목록 파일에 저장한다. `--source`의 기본값은 `~/3gpp-specs/`다. 목록은 줄마다 규격 번호 하나를 적는 UTF-8 텍스트이며, `23.501`과 `38.101-1`처럼 작성하거나 편집할 수 있다. `download --list`에 목록 경로를 넘겨 다시 사용한다. 저장 위치를 바꾸려면 `download --output`을 사용한다.
