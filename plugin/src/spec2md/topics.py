"""topics/topics.json -> topics/{id}.md (output-contract.md section 6)."""
import json
import os

from .split import _q


def _strip_front_matter(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end >= 0:
            return text[end + 4:].lstrip("\n")
    return text


def build_topics(spec_dir):
    man = json.load(open(os.path.join(spec_dir, "manifest.json"), encoding="utf-8"))
    tpath = os.path.join(spec_dir, "topics", "topics.json")
    topics = json.load(open(tpath, encoding="utf-8"))
    by_clause = {}
    for c in man["clauses"]:
        by_clause.setdefault(c["clause"], []).append(c)
    written = 0
    for t in topics.get("topics", []):
        tid = t["id"]
        if not tid or "/" in tid or "\\" in tid or tid.startswith("."):
            raise ValueError(f"bad topic id {tid!r}")
        lines = ["---",
                 f"spec: {_q(man['spec'])}",
                 f"version: {_q(man['version'])}",
                 f"topic: {_q(tid)}",
                 f"title: {_q(t.get('title', tid))}",
                 f"clauses: {_q(t.get('clauses', []))}",
                 "---", ""]
        parts = []
        for clause in t.get("clauses", []):
            for c in by_clause.get(clause, []):
                if not c.get("file"):
                    continue
                body = open(os.path.join(spec_dir, c["file"]), encoding="utf-8").read()
                parts.append(f"<!-- source: {c['file']} -->\n\n" + _strip_front_matter(body).rstrip("\n"))
        with open(os.path.join(spec_dir, "topics", f"{tid}.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n\n".join(parts) + "\n")
        written += 1
    return written
