#!/usr/bin/env python3
"""Check raw/{spec}/topics/topics.json against manifest.json (stdlib only).

Usage: python check_topics.py raw/38331-i10
Exit 0 = every clause with a file is covered and no unknown clause ids; 1 otherwise.
"""
import json
import os
import re
import sys

ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    d = sys.argv[1]
    man = json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8"))
    top = json.load(open(os.path.join(d, "topics", "topics.json"), encoding="utf-8"))
    chars = {c["clause"]: int(c.get("chars", 0) or 0) for c in man["clauses"]}
    body = {c["clause"] for c in man["clauses"] if c.get("file")}
    topics = top.get("topics", [])
    used = {x for t in topics for x in t.get("clauses", [])}
    unc = set(top.get("uncategorized", []))
    problems = []
    missing = sorted(body - used - unc)
    unknown = sorted((used | unc) - set(chars))
    if missing:
        problems.append(f"{len(missing)} clauses with content not assigned: {missing[:50]}")
    if unknown:
        problems.append(f"{len(unknown)} clause ids not in manifest: {unknown[:50]}")
    ids = [t.get("id", "") for t in topics]
    bad = [i for i in ids if not ID_RE.match(i)]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if bad:
        problems.append(f"invalid topic ids (use kebab-case): {bad[:20]}")
    if dup:
        problems.append(f"duplicate topic ids: {dup}")
    known = set(ids)
    dangling = sorted({r for t in topics for r in t.get("related", []) if r not in known})
    print(f"topics={len(topics)} assigned={len(used & body)}/{len(body)} uncategorized={len(unc)}")
    for t in topics:
        size = sum(chars.get(c, 0) for c in t.get("clauses", []))
        flag = "  <-- large" if size > 200000 else ("  <-- tiny" if len(t.get("clauses", [])) < 2 else "")
        print(f"  {t.get('id')}: {len(t.get('clauses', []))} clauses, {size} chars{flag}")
    if dangling:
        print(f"NOTE related ids not defined here (ok if renamed/old ids): {dangling[:20]}")
    for p in problems:
        print(f"ERROR {p}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
