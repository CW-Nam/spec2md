#!/usr/bin/env python3
"""Lint a spec2md LLM wiki (stdlib only; must not import spec2md).

Usage:
  python lint_wiki.py WIKI [--json OUT.json]

Pages are WIKI/**/*.md except SCHEMA.md, index.md, log.md (at any depth).

ERROR checks
  * every relative markdown link `[text](href)` resolves to an existing file
    (relative to the page's own folder); a `#anchor` must match an
    `<a id="...">` in the target or a GitHub-style slug of one of its headings
    (lowercase, punctuation other than space/hyphen removed, spaces -> hyphens)
  * front matter (`---` block of `key: value` lines) has type, title, sources,
    specs, updated; `sources` (one-line JSON array) is non-empty; `type` is one
    of feature|concept|spec|answer
  * every page is linked from index.md (links resolved relative to index.md)
  * every log.md line starting with `## [` matches
    `## [YYYY-MM-DD] (ingest|query|lint) | text`
WARN checks
  * orphan: no incoming link from another wiki page (index.md/log.md/SCHEMA.md
    do not count)
  * source-less prose: >= 5 body paragraphs with no link whose href contains
    `linked/`. A paragraph is a blank-line-separated block of the body (front
    matter, fenced code and HTML comments removed) that does not start with
    `#`, `-`, `*`, `>`, `|`, `<` or a numbered-list marker.

Links are ignored inside fenced code blocks, inline code and HTML comments;
external links (scheme: http, https, mailto, ...) are skipped.

Exit code: 0 = no errors, 1 = errors found, 2 = bad input.
"""
import argparse
import json
import os
import posixpath
import re
import sys
from urllib.parse import unquote

SPECIAL = {"SCHEMA.md", "index.md", "log.md"}
REQUIRED = ("type", "title", "sources", "specs", "updated")
TYPES = ("feature", "concept", "spec", "answer")
LOG_RE = re.compile(r"^## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint) \| .+$")
FENCE_RE = re.compile(r"^ {0,3}(```|~~~)")
INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1).)+?\1", re.S)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
LINK_RE = re.compile(r"\[[^\]]*\]\(\s*<?([^)\s>]*)>?(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
ID_RE = re.compile(r'<a\s+id="([^"\n]+)"')
HEADING_RE = re.compile(r"^ {0,3}#{1,6}[ \t]+(.+?)[ \t]*#*[ \t]*$")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
LIST_START_RE = re.compile(r"^\d+[.)]\s")


def strip_fences(text):
    """Blank out fenced code lines (keeps line numbers)."""
    out, fence = [], None
    for line in text.split("\n"):
        m = FENCE_RE.match(line)
        if fence:
            if m and m.group(1) == fence:
                fence = None
            out.append("")
        elif m:
            fence = m.group(1)
            out.append("")
        else:
            out.append(line)
    return "\n".join(out)


def blank(m):
    return re.sub(r"[^\n]", " ", m.group(0))


def prose(text):
    """Text with fenced code, HTML comments and inline code blanked (same line numbers)."""
    t = strip_fences(text)
    t = COMMENT_RE.sub(blank, t)
    return INLINE_CODE_RE.sub(blank, t)


def split_front(text):
    """-> (dict of raw values or None if absent, text with front matter lines blanked)."""
    lines = text.split("\n")
    if lines[0].rstrip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            fm = {}
            for ln in lines[1:i]:
                k, sep, v = ln.partition(":")
                if sep and k.strip():
                    fm[k.strip()] = v.strip()
            return fm, "\n" * (i + 1) + "\n".join(lines[i + 1:])
    return None, text


def slug(heading):
    h = heading.strip().lower()
    h = re.sub(r"[^\w\- ]", "", h)
    return h.replace(" ", "-")


class Linter:
    def __init__(self, wiki):
        self.wiki = wiki
        self.errors, self.warnings = [], []
        self._anchors = {}

    def err(self, kind, where, msg):
        self.errors.append({"kind": kind, "where": where, "message": msg})

    def anchors(self, path):
        if path not in self._anchors:
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except (OSError, UnicodeDecodeError):
                self._anchors[path] = None
                return None
            ids = set(ID_RE.findall(text))
            seen = {}
            for line in strip_fences(text).split("\n"):
                m = HEADING_RE.match(line)
                if m:
                    s = slug(re.sub(r"<[^>]+>|[*_`]", "", m.group(1)))
                    n = seen.get(s, 0)
                    seen[s] = n + 1
                    ids.add(s if n == 0 else f"{s}-{n}")
            self._anchors[path] = ids
        return self._anchors[path]

    def links(self, text):
        """-> [(href, line)] of non-external markdown links."""
        t = prose(text)
        out = []
        for m in LINK_RE.finditer(t):
            href = m.group(1)
            if not href or SCHEME_RE.match(href):
                continue
            out.append((href, t.count("\n", 0, m.start()) + 1))
        return out

    def resolve(self, rel, href):
        """-> (wiki-relative normalized path or None if outside wiki, abs path, anchor)."""
        path, _, anchor = href.partition("#")
        path, anchor = unquote(path), unquote(anchor)
        if not path:
            return rel, os.path.join(self.wiki, *rel.split("/")), anchor
        norm = posixpath.normpath(posixpath.join(posixpath.dirname(rel), path))
        ap = os.path.normpath(os.path.join(self.wiki, *norm.split("/")))
        return (None if norm.startswith("..") else norm), ap, anchor

    def check_links(self, rel, text):
        """Check the links of one file; returns the set of wiki-relative targets."""
        targets = set()
        for href, line in self.links(text):
            norm, ap, anchor = self.resolve(rel, href)
            where = f"{rel}:{line}"
            if not os.path.isfile(ap):
                self.err("broken_link", where, f"broken link: file not found: {href}")
                continue
            if norm:
                targets.add(norm)
            if anchor and ap.endswith(".md"):
                ids = self.anchors(ap)
                if ids is None or anchor not in ids:
                    self.err("broken_link", where, f"broken link: anchor not found: {href}")
        return targets

    def check_front(self, rel, fm):
        if fm is None:
            fm = {}
        for k in REQUIRED:
            if k not in fm:
                self.err("front_matter", rel, f"{rel}: missing front matter key: {k}")
        if "sources" in fm:
            try:
                src = json.loads(fm["sources"])
            except ValueError:
                src = None
            if not isinstance(src, list) or not src:
                self.err("empty_sources", rel, f"{rel}: empty sources (need a non-empty JSON array)")
        if "type" in fm and fm["type"] not in TYPES:
            self.err("bad_type", rel, f"{rel}: bad type {fm['type']!r} (expected {'|'.join(TYPES)})")

    def source_less_paragraphs(self, body):
        n = 0
        for block in re.split(r"\n[ \t]*\n", prose(body)):
            b = block.strip()
            if not b or b[0] in "#-*>|<" or LIST_START_RE.match(b):
                continue
            if not any("linked/" in h for h, _ in self.links(b)):
                n += 1
        return n


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read().replace("\r\n", "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Lint a spec2md LLM wiki.")
    ap.add_argument("wiki")
    ap.add_argument("--json", dest="json_out")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.wiki):
        print(f"error: not a directory: {a.wiki}", file=sys.stderr)
        return 2
    wiki = os.path.abspath(a.wiki)
    pages = []
    for d, dirs, files in os.walk(wiki):
        dirs.sort()
        for fn in sorted(files):
            if fn.endswith(".md"):
                pages.append(os.path.relpath(os.path.join(d, fn), wiki).replace(os.sep, "/"))
    pages.sort()
    content = [p for p in pages if posixpath.basename(p) not in SPECIAL]
    L = Linter(wiki)

    incoming = {p: set() for p in content}
    for rel in content:
        text = read(os.path.join(wiki, *rel.split("/")))
        fm, body = split_front(text)
        L.check_front(rel, fm)
        for t in L.check_links(rel, text):
            if t in incoming and t != rel:
                incoming[t].add(rel)
        n = L.source_less_paragraphs(body)
        if n >= 5:
            L.warnings.append(f"{rel}: {n} body paragraphs without a source link into linked/")

    idx = os.path.join(wiki, "index.md")
    indexed = set()
    if os.path.isfile(idx):
        indexed = L.check_links("index.md", read(idx))
    else:
        L.err("no_index", "index.md", "index.md: missing")
    for rel in content:
        if rel not in indexed:
            L.err("not_in_index", rel, f"{rel}: not in index.md")

    log = os.path.join(wiki, "log.md")
    if os.path.isfile(log):
        for i, line in enumerate(strip_fences(read(log)).split("\n"), 1):
            if line.startswith("## [") and not LOG_RE.match(line):
                L.err("bad_log", f"log.md:{i}", f"log.md:{i}: bad log entry: {line}")

    for rel in content:
        if not incoming[rel]:
            L.warnings.append(f"{rel}: orphan page (no incoming link from another page)")

    summary = {"pages": len(content), "errors": len(L.errors), "warnings": len(L.warnings)}
    for e in L.errors:
        if e["where"].split(":")[0] in e["message"]:
            print(f"ERROR {e['message']}")
        else:
            print(f"ERROR {e['where']}: {e['message']}")
    for w in L.warnings:
        print(f"WARN {w}")
    print(f"checked {summary['pages']} pages: {summary['errors']} errors, {summary['warnings']} warnings")
    if a.json_out:
        rep = {"summary": summary, "errors": L.errors, "warnings": L.warnings}
        os.makedirs(os.path.dirname(os.path.abspath(a.json_out)), exist_ok=True)
        with open(a.json_out, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rep, sort_keys=True, ensure_ascii=False, indent=1) + "\n")
    return 1 if L.errors else 0


if __name__ == "__main__":
    sys.exit(main())
