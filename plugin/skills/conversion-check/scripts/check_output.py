#!/usr/bin/env python3
"""Check a spec2md output directory against the source outline (stdlib only).

This is a *structural fidelity* check (nothing lost, nothing broken), not a
check of technical correctness of the spec content.

Usage:
  python inspect_docx.py SPEC.docx --json _workspace/inspect.json
  python check_output.py --inspect _workspace/inspect.json --out raw/38331-i10 [--json report.json]

Exit code: 0 = no errors (warnings allowed), 1 = errors found, 2 = bad input.
"""
import argparse
import json
import os
import re
import sys

REQUIRED_FM = ["spec", "version", "clause", "title", "level", "source_file"]
REQUIRED_MANIFEST = ["spec", "version", "source_files", "split_depth", "clauses"]
IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)|<img\s[^>]*?src=\"([^\"]+)\"")
RESIDUE_RE = re.compile(r"<w:|</w:|\x07|\x0b|�")
PUA_RE = re.compile(r"[-]")  # unmapped Symbol/Wingdings font characters
# headings normally skipped as front matter (cover page, table of contents)
SKIP_TITLES = {"contents", "table of contents"}


def is_change_history(title):
    """The 'Change history' annex is not converted (output-contract.md section 5)."""
    return title.strip().rstrip(":").strip().lower() == "change history"


def drop_change_history(outline):
    """Remove change history headings and the headings under them."""
    kept, skip_level = [], None
    for h in outline:
        if skip_level is not None and h["level"] > skip_level:
            continue
        skip_level = h["level"] if is_change_history(h["title"]) else None
        if skip_level is None:
            kept.append(h)
    return kept


def read_front_matter(text):
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    fm = {}
    for line in text[3:end].splitlines():
        if ":" in line and not line.startswith((" ", "-", "#")):
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def key_of(h):
    """Numbered clause -> its number; unnumbered heading -> slug of its title."""
    return h.get("clause") or slugify(h.get("title"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inspect", required=True, help="JSON from inspect_docx.py --json")
    ap.add_argument("--out", required=True, help="spec2md output directory (contains manifest.json)")
    ap.add_argument("--max-chars", type=int, default=60000, help="warn when a file body exceeds this")
    ap.add_argument("--min-chars", type=int, default=40, help="warn when a file body is shorter than this")
    ap.add_argument("--json", help="write the report as JSON")
    a = ap.parse_args()

    errors, warnings, info = [], [], {}
    try:
        src = json.load(open(a.inspect, encoding="utf-8"))
        man = json.load(open(os.path.join(a.out, "manifest.json"), encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: cannot read input: {e}", file=sys.stderr)
        sys.exit(2)

    # 1. manifest shape
    for k in REQUIRED_MANIFEST:
        if k not in man:
            errors.append(f"manifest.json missing key '{k}'")
    clauses = man.get("clauses", [])
    depth = int(man.get("split_depth", 3))
    src_files = src.get("source_files") or [src.get("source_file")]
    if "source_files" in man and list(man["source_files"]) != list(src_files):
        errors.append(f"manifest source_files {man['source_files']} != inspected parts {src_files}")

    # 2. outline coverage
    outline = drop_change_history(
        [h for h in src.get("outline", []) if h["title"].strip().lower() not in SKIP_TITLES])
    got_keys = [key_of(c) for c in clauses]
    got_set = set(got_keys)
    all_keys = {key_of(h) for h in outline}
    # level<=depth headings are required; deeper ones are allowed (--max-chars auto-split)
    expected = [h for h in outline if h["level"] <= depth or key_of(h) in got_set]
    exp_keys = [key_of(h) for h in expected]
    exp_set = set(exp_keys)
    missing = [k for k in exp_keys if k not in got_set]
    extra = [k for k in got_keys if k not in all_keys]
    deeper = sum(1 for c in clauses if int(c.get("level") or 0) > depth)
    if deeper:
        info["auto_split_entries"] = deeper
    if missing:
        errors.append(f"{len(missing)} source headings (level<={depth}) not in manifest: {missing[:20]}")
    if extra:
        warnings.append(f"{len(extra)} manifest clauses not found in source outline: {extra[:20]}")
    common = [k for k in got_keys if k in exp_set]
    exp_order = [k for k in exp_keys if k in got_set]
    if common != exp_order:
        warnings.append("clause order in manifest differs from source order")
    dup = sorted({k for k in got_keys if got_keys.count(k) > 1}) if len(got_keys) < 20000 else []
    if dup:
        warnings.append(f"duplicate clause keys in manifest: {dup[:20]}")

    # 3. files, front matter, content hygiene
    referenced = set()
    sizes = []
    fence_bad, residue, broken_img, pua, asn1_out = [], [], [], [], 0
    for c in clauses:
        rel = c.get("file")
        if not rel:
            continue
        referenced.add(os.path.normpath(rel))
        p = os.path.join(a.out, rel)
        if not os.path.isfile(p):
            errors.append(f"manifest file missing on disk: {rel}")
            continue
        raw = open(p, "rb").read()
        if raw.startswith(b"\xef\xbb\xbf"):
            warnings.append(f"UTF-8 BOM present (write files without BOM): {rel}")
        text = raw.decode("utf-8-sig", errors="replace").replace("\r\n", "\n")
        fm = read_front_matter(text)
        if fm is None:
            errors.append(f"no front matter: {rel}")
        else:
            lack = [k for k in REQUIRED_FM if k not in fm]
            if lack:
                errors.append(f"front matter missing {lack}: {rel}")
            elif c.get("clause") and fm["clause"] != c["clause"]:
                errors.append(f"front matter clause {fm['clause']} != manifest {c['clause']}: {rel}")
            elif c.get("source_file") and fm["source_file"] != c["source_file"]:
                errors.append(f"front matter source_file {fm['source_file']} != manifest {c['source_file']}: {rel}")
        body = text.split("\n---", 1)[-1] if fm is not None else text
        sizes.append((len(body), rel))
        if body.count("```") % 2:
            fence_bad.append(rel)
        if RESIDUE_RE.search(body):
            residue.append(rel)
        asn1_out += body.count("ASN1START")
        if PUA_RE.search(body):
            pua.append(rel)
        for md_t, html_t in IMG_RE.findall(body):
            target = md_t or html_t
            if target.startswith(("http://", "https://")):
                continue
            if not os.path.isfile(os.path.normpath(os.path.join(os.path.dirname(p), target))):
                broken_img.append(f"{rel} -> {target}")

    for root, _, files in os.walk(os.path.join(a.out, "clauses")):
        for fn in files:
            if fn.endswith(".md"):
                rel = os.path.normpath(os.path.relpath(os.path.join(root, fn), a.out))
                if rel not in referenced:
                    warnings.append(f"orphan file not in manifest: {rel}")

    if fence_bad:
        errors.append(f"unbalanced ``` code fences in {len(fence_bad)} files: {fence_bad[:10]}")
    if residue:
        errors.append(f"XML/control-char residue in {len(residue)} files: {residue[:10]}")
    if broken_img:
        errors.append(f"{len(broken_img)} broken image links: {broken_img[:10]}")
    if pua:
        warnings.append(f"private-use characters (unmapped w:sym / Symbol font) in {len(pua)} files: {pua[:10]}")

    # 4. element counts vs source
    def total(key):
        return sum(int(c.get(key, 0) or 0) for c in clauses)
    src_tables = src.get("tables", {}).get("body_level", 0) - src.get("tables", {}).get("change_history", 0)
    if total("tables") != src_tables:
        warnings.append(f"tables: source {src_tables} vs manifest {total('tables')} "
                        "(cover/front-matter tables may be skipped intentionally)")
    src_asn1 = src.get("asn1_start_markers", 0)
    if src_asn1 and asn1_out != src_asn1:
        errors.append(f"ASN1START markers: source {src_asn1} vs output {asn1_out}")
    src_eq = int(src.get("equations", 0)) + int(src.get("equation_objects", 0))
    if total("equations") < src_eq:
        warnings.append(f"equations: source OMML+OLE {src_eq} vs manifest {total('equations')}")
    src_fig = sum(src.get("figures", {}).values())
    if total("figures") < src_fig * 0.9:
        warnings.append(f"figures: source objects {src_fig} vs manifest {total('figures')}")

    # 5. size distribution (chunk sizing for LLM ingestion)
    if sizes:
        s = sorted(x for x, _ in sizes)
        info["files"] = len(s)
        info["body_chars"] = {"min": s[0], "median": s[len(s) // 2], "max": s[-1]}
        big = [r for n, r in sizes if n > a.max_chars]
        tiny = [r for n, r in sizes if n < a.min_chars]
        if big:
            warnings.append(f"{len(big)} files > {a.max_chars} chars (consider deeper split): {big[:10]}")
        if tiny:
            warnings.append(f"{len(tiny)} files < {a.min_chars} chars: {tiny[:10]}")
    info["expected_headings"] = len(expected)
    info["manifest_clauses"] = len(clauses)

    report = {"ok": not errors, "errors": errors, "warnings": warnings, "info": info}
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
    print(f"RESULT: {'PASS' if not errors else 'FAIL'}  errors={len(errors)} warnings={len(warnings)}")
    for e in errors:
        print(f"  ERROR   {e}")
    for w in warnings:
        print(f"  WARNING {w}")
    print(f"  INFO    {json.dumps(info)}")
    sys.exit(0 if not errors else 1)


if __name__ == "__main__":
    main()
