"""합성 raw 출력(spec 폴더)을 만드는 테스트 헬퍼."""
import json
import os
import re


def _slug(title):
    return re.sub(r"[^0-9a-z]+", "-", title.lower()).strip("-")[:60]


def make_spec(root, code, spec_number, version, clauses):
    """clauses: dict(clause, title, level, parent, file, body) 목록. file=None이면 본문 없음.

    file은 'clauses/…' 상대 경로 문자열. body는 제목 줄 뒤에 붙는 본문.
    spec 폴더 경로를 돌려준다.
    """
    spec_dir = os.path.join(str(root), code)
    os.makedirs(os.path.join(spec_dir, "clauses"), exist_ok=True)
    major = int(version.split(".")[0])
    release = f"Rel-{major}"
    source = code + ".docx"
    entries = []
    for order, c in enumerate(clauses, start=1):
        entry = {
            "order": order, "clause": c["clause"], "title": c["title"],
            "level": c["level"], "parent": c.get("parent"),
            "source_file": source, "file": c.get("file"),
            "tables": 0, "figures": 0, "code_blocks": 0, "equations": 0, "chars": 0,
        }
        if c.get("file"):
            parent = json.dumps(c.get("parent"))
            fm = (
                "---\n"
                f'spec: "TS {spec_number}"\n'
                f'spec_number: "{spec_number}"\n'
                f'version: "{version}"\n'
                f'release: "{release}"\n'
                f'clause: "{c["clause"]}"\n'
                f'title: "{c["title"]}"\n'
                f'level: {c["level"]}\n'
                f"parent: {parent if c.get('parent') else 'null'}\n"
                f'path: ["{c["clause"]} {c["title"]}"]\n'
                f'source_file: "{source}"\n'
                "---\n"
            )
            text = fm + f'# {c["clause"]} {c["title"]}\n\n' + c.get("body", "")
            entry["chars"] = len(text)
            with open(os.path.join(spec_dir, c["file"]), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        entries.append(entry)
    manifest = {
        "spec": f"TS {spec_number}", "spec_number": spec_number,
        "version": version, "release": release,
        "source_files": [source], "tool_version": "0.1.0",
        "split_depth": 3, "skipped": [], "clauses": entries,
    }
    with open(os.path.join(spec_dir, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return spec_dir
