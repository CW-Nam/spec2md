#!/usr/bin/env python3
"""Independent checker for `spec2md link` output (stdlib only; must not import spec2md).

Usage:
  python check_links.py LINKED --raw RAW [--json OUT.json]

ERROR checks
  * anchored links are semantically right: text number N <-> anchor table-N /
    figure-N / clause-N (keyword Table/Figure/clause/subclause/section/Annex, either
    initial case, singular or plural, must match)
  * every markdown link / <a href> that points to a .md file: the file exists
    in LINKED and the #anchor exists there as an `<a id="..."></a>` line
  * undoing the linker's changes (backlinks section, anchor lines, generated
    links, media prefix) gives the raw file byte for byte
  * every raw body file (manifest "file") exists in LINKED
WARN output
  * per-spec status distribution (from LINKED/{code}/refs.json) and the top 20
    `missing_target` as (target_spec, kind, target_id, count)

Reversal only undoes what the linker can have produced: links whose href ends
with `.md` / `.md#...` and whose text is reference-shaped (optional
clause/Table/Figure/Annex word + number). Other links in raw are left alone.
Limitation: a raw file that itself contained such a link or an anchor line of
the form `<a id="table-|figure-|clause-...">` would be reported as differing.

Exit code: 0 = no errors, 1 = errors found, 2 = bad input.
"""
import argparse
import json
import os
import posixpath
import re
import sys

MARKER = "<!-- spec2md:backlinks -->"
SEP = "\n\n" + MARKER
ANCHOR_LINE_RE = re.compile(r'^<a id="(?:table|figure|clause)-[^"\n]*"></a>\n', re.M)
ID_RE = re.compile(r'<a id="([^"\n]+)"></a>')
_HREF = r"[^)\s\"]*\.md(?:#[^)\s\"]*)?"
_WORD = r"[Tt]ables?|[Ff]igures?|[Cc]lauses?|[Ss]ubclauses?|[Ss]ections?|[Aa]nnex(?:es)?"
_TEXT = rf"(?:(?:{_WORD})[^\S\n]+)?[0-9A-Z][0-9A-Za-z.\-]*"
MD_LINK_RE = re.compile(rf"\[({_TEXT})\]\(({_HREF})\)")
A_LINK_RE = re.compile(rf'<a href="({_HREF})">({_TEXT})</a>')
CHECK_MD_RE = re.compile(rf"\]\(({_HREF})\)")
CHECK_A_RE = re.compile(rf'<a href="({_HREF})">')
_KEYWORD_RE = re.compile(rf"(?:({_WORD})[^\S\n]+)?([0-9A-Z][0-9A-Za-z.\-]*)\Z")
_KIND = {"table": "table", "figure": "figure", "clause": "clause", "subclause": "clause",
         "section": "clause", "annex": "clause", "annexe": "clause"}
STATUSES = ("resolved", "missing_target", "missing_spec", "ambiguous")


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def media_prefix(raw_root, linked_root, code):
    rel = os.path.relpath(os.path.join(os.path.abspath(raw_root), code, "media"),
                          os.path.join(os.path.abspath(linked_root), code, "clauses"))
    return rel.replace(os.sep, "/") + "/"


def reverse(text, prefix):
    """Undo the linker: backlinks section, media prefix, generated links, anchor lines."""
    i = text.find(SEP)
    if i >= 0:
        text = text[:i] + "\n"
    text = text.replace("](" + prefix, "](../media/").replace('src="' + prefix, 'src="../media/')
    text = MD_LINK_RE.sub(lambda m: m.group(1), text)
    text = A_LINK_RE.sub(lambda m: m.group(2), text)
    return ANCHOR_LINE_RE.sub("", text)


def first_diff(a, b):
    n = min(len(a), len(b))
    pos = next((k for k in range(n) if a[k] != b[k]), n)
    line = a.count("\n", 0, pos) + 1
    return pos, line


def spec_dirs(root):
    return sorted(d for d in os.listdir(root)
                  if os.path.isfile(os.path.join(root, d, "manifest.json")))


class Checker:
    def __init__(self, linked, raw):
        self.linked, self.raw = linked, raw
        self.errors, self.warnings = [], []
        self._ids = {}

    def err(self, kind, where, msg):
        self.errors.append({"kind": kind, "where": where, "message": msg})

    def ids(self, path):
        if path not in self._ids:
            try:
                self._ids[path] = set(ID_RE.findall(read_bytes(path).decode("utf-8")))
            except OSError:
                self._ids[path] = None
        return self._ids[path]

    def check_links(self, code, rel, text):
        base = posixpath.dirname(posixpath.join(code, rel))
        hrefs = [(m.group(1), text.count("\n", 0, m.start()) + 1) for m in CHECK_MD_RE.finditer(text)]
        hrefs += [(m.group(1), text.count("\n", 0, m.start()) + 1) for m in CHECK_A_RE.finditer(text)]
        where_f = f"{code}/{rel}"
        for href, line in hrefs:
            path, _, anchor = href.partition("#")
            target = posixpath.normpath(posixpath.join(base, path))
            tcode = target.split("/", 1)[0]
            tpath = os.path.join(self.linked, *target.split("/"))
            if target.startswith("..") or not os.path.isfile(tpath):
                partial = (not target.startswith("..")
                           and not os.path.isfile(os.path.join(self.linked, tcode, "manifest.json"))
                           and os.path.isfile(os.path.join(self.raw, *target.split("/"))))
                if partial:
                    self.warnings.append(f"{where_f}:{line}: link target spec {tcode} is not in LINKED "
                                         f"(partial run?): {href}")
                else:
                    self.err("broken_link", f"{where_f}:{line}", f"broken link: file not found: {href}")
                continue
            if anchor:
                ids = self.ids(tpath)
                if ids is None or anchor not in ids:
                    self.err("broken_anchor", f"{where_f}:{line}", f"broken anchor: {href}")

    def check_semantics(self, code, rel, text):
        """Anchor must be {table|figure|clause}-N with the same N as the link text."""
        where_f = f"{code}/{rel}"
        pairs = [(m.group(2), m.group(1), m.start()) for m in MD_LINK_RE.finditer(text)]
        pairs += [(m.group(1), m.group(2), m.start()) for m in A_LINK_RE.finditer(text)]
        for href, label, pos in pairs:
            anchor = href.partition("#")[2]
            if not anchor:
                continue
            m = _KEYWORD_RE.match(label)
            kind, _, ident = anchor.partition("-")
            ok = m is not None and ident == m.group(2) and kind in ("table", "figure", "clause")
            if ok and m.group(1):
                ok = _KIND[m.group(1).lower().rstrip("s")] == kind
            if not ok:
                line = text.count("\n", 0, pos) + 1
                self.err("anchor_mismatch", f"{where_f}:{line}",
                         f"anchor mismatch: text {label!r} links to #{anchor}")

    def check_spec(self, code):
        info = {"files": 0, "status": {s: 0 for s in STATUSES}}
        rman_path = os.path.join(self.raw, code, "manifest.json")
        if not os.path.isfile(rman_path):
            self.err("no_raw", code, f"{code}: spec exists in LINKED but not in raw")
            return info
        rman = load_json(rman_path)
        lman = load_json(os.path.join(self.linked, code, "manifest.json"))
        prefix = media_prefix(self.raw, self.linked, code)
        for e in rman.get("clauses", []):
            rel = e.get("file")
            if not rel:
                continue
            where = f"{code}/{rel}"
            lpath = os.path.join(self.linked, code, *rel.split("/"))
            if not os.path.isfile(lpath):
                self.err("missing", where, f"missing in LINKED: {where}")
                continue
            info["files"] += 1
            ltext = read_bytes(lpath).decode("utf-8")
            self.check_links(code, rel, ltext)
            self.check_semantics(code, rel, ltext)
            want = read_bytes(os.path.join(self.raw, code, *rel.split("/")))
            got = reverse(ltext, prefix).encode("utf-8")
            if got != want:
                pos, line = first_diff(got.decode("utf-8", "replace"), want.decode("utf-8", "replace"))
                self.err("differs", where,
                         f"{where}: reversed linked file differs from raw "
                         f"(first difference at char {pos}, line {line})")
        if lman.get("spec_number") != rman.get("spec_number"):
            self.err("manifest", code, f"{code}: manifest spec_number differs from raw")
        return info

    def check_refs(self, code, info, missing):
        p = os.path.join(self.linked, code, "refs.json")
        if not os.path.isfile(p):
            self.err("no_refs", code, f"{code}: refs.json missing")
            return
        for r in load_json(p).get("refs", []):
            info["status"][r["status"]] = info["status"].get(r["status"], 0) + 1
            if r["status"] == "missing_target":
                k = (r.get("target_spec"), r.get("kind"), r.get("target_id"))
                missing[k] = missing.get(k, 0) + 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check spec2md link output against raw.")
    ap.add_argument("linked")
    ap.add_argument("--raw", required=True)
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--max-print", type=int, default=100)
    a = ap.parse_args(argv)
    for d in (a.linked, a.raw):
        if not os.path.isdir(d):
            print(f"error: not a directory: {d}", file=sys.stderr)
            return 2
    c = Checker(a.linked, a.raw)
    codes = spec_dirs(a.linked)
    if not codes:
        print(f"error: no spec folders (manifest.json) in {a.linked}", file=sys.stderr)
        return 2
    specs, missing = {}, {}
    for code in codes:
        specs[code] = c.check_spec(code)
        c.check_refs(code, specs[code], missing)
    for code in spec_dirs(a.raw):
        if code not in specs:
            c.warnings.append(f"{code}: in raw but not in LINKED (not checked)")
    top = sorted(missing.items(), key=lambda kv: (-kv[1], str(kv[0])))[:20]
    top_rows = [{"target_spec": k[0], "kind": k[1], "target_id": k[2], "count": n} for k, n in top]
    files = sum(s["files"] for s in specs.values())
    for code, s in specs.items():
        st = " ".join(f"{k}={s['status'].get(k, 0)}" for k in STATUSES)
        c.warnings.append(f"{code}: {s['files']} files, refs {st}")
    for row in top_rows:
        c.warnings.append(f"missing_target ({row['target_spec']}, {row['kind']}, {row['target_id']}): "
                          f"{row['count']}")
    summary = {"specs": len(specs), "files": files, "errors": len(c.errors),
               "warnings": len(c.warnings)}
    for e in c.errors[:a.max_print]:
        print(f"ERROR {e['where']}: {e['message']}" if not e["message"].startswith(e["where"])
              and e["where"] not in e["message"] else f"ERROR {e['message']}")
    if len(c.errors) > a.max_print:
        print(f"... {len(c.errors) - a.max_print} more errors (see --json)")
    for w in c.warnings:
        print(f"WARN {w}")
    print(f"checked {summary['specs']} specs, {files} files: {len(c.errors)} errors, "
          f"{len(c.warnings)} warnings")
    if a.json_out:
        rep = {"summary": summary, "errors": c.errors, "warnings": c.warnings,
               "specs": specs, "missing_target": top_rows}
        os.makedirs(os.path.dirname(os.path.abspath(a.json_out)), exist_ok=True)
        with open(a.json_out, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rep, sort_keys=True, ensure_ascii=False, indent=1) + "\n")
    return 1 if c.errors else 0


if __name__ == "__main__":
    sys.exit(main())
