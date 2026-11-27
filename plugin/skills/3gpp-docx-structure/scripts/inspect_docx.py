#!/usr/bin/env python3
"""Inspect the structure of a 3GPP specification .docx (stdlib only).

Streams word/document.xml so that very large specs (e.g. TS 38.331) do not
need to be loaded into memory at once.

Usage:
  python inspect_docx.py SPEC.docx                 # human-readable summary
  python inspect_docx.py SPEC.docx --json OUT.json # full report (used by check_output.py)
  python inspect_docx.py SPEC.docx --samples 3     # sample texts per style
  python inspect_docx.py P1.docx P2.docx ... --json OUT.json
      # multi-part spec: parts are merged in sorted file-name order into one
      # report (outline order continues across parts; see output-contract.md)
"""
import argparse
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
O = "{urn:schemas-microsoft-com:office:office}"
MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"
# source typo "5. 2.2.4.2.3<TAB>Title" (36.133): a space after the first dot splits the number
SPLIT_NUM_RE = re.compile(r"^(\d+[A-Za-z]{0,2}\d*)\.\s+(\d+[A-Za-z]{0,2}\d*(?:\.\d+[A-Za-z]{0,2}\d*)+)(?=\t)")
# "heading 3" (Word built-in) and 3GPP custom "H6" (defined with outlineLvl 9 = body text)
HEADING_RE = re.compile(r"^(?:heading\s*|header\s*|h)(\d)$", re.I)  # "Header 6": custom style in 38101-5
# "5.3.5", "A.1.2", "Annex A (normative):", "Foreword"
# letter-suffixed numbers too: 5.2.2.3.3a, 5.3.5.13b1, 5.8.9.1a.1.1
# 4.3A, 9.4.1a, 5.3.5.13b1, B.2.3B.4A, F.5.F, trailing dot "6.3.3.1.", NBSP separator
CLAUSE_RE = re.compile(r"^\s*((?:[A-Z]{1,2}|\d+[A-Za-z]{0,2}\d*)(?:\.(?:\d+[A-Za-z]{0,2}\d*|[A-Z]))*)\.?:?[\s ]+(.+)$")
ANNEX_RE = re.compile(r"^\s*Annex\s+([A-Z]{1,2})\b\s*(.*)$", re.I)


def load_styles(z):
    """Return styleId -> (name, outline_level or None)."""
    styles = {}
    try:
        root = ET.fromstring(z.read("word/styles.xml"))
    except KeyError:
        return styles
    for s in root.iter(W + "style"):
        sid = s.get(W + "styleId")
        name_el = s.find(W + "name")
        name = name_el.get(W + "val") if name_el is not None else sid
        lvl = None
        ppr = s.find(W + "pPr")
        if ppr is not None:
            ol = ppr.find(W + "outlineLvl")
            if ol is not None:
                lvl = _outline_level(ol)
        styles[sid] = (name, lvl)
    return styles


def _outline_level(ol):
    """w:outlineLvl val 0-8 -> level 1-9; val 9 means 'body text' (no level)."""
    v = int(ol.get(W + "val"))
    return v + 1 if v < 9 else None


def norm_heading(text):
    """Heading text with line breaks folded to one space (contract: titles are one line)."""
    return re.sub(r"[ \t]*\n\s*", " ", text.strip())


def para_text(p):
    parts = []
    for el in p.iter():
        tag = el.tag
        if tag in (W + "t", M + "t") and el.text:  # math text kept so headings are not truncated
            parts.append(el.text)
        elif tag == W + "tab":
            parts.append("\t")
        elif tag in (W + "br", W + "cr"):
            parts.append("\n")
    return "".join(parts)


def para_style(p, styles):
    ppr = p.find(W + "pPr")
    sid = None
    if ppr is not None:
        ps = ppr.find(W + "pStyle")
        if ps is not None:
            sid = ps.get(W + "val")
    name, lvl = styles.get(sid, (sid or "Normal", None)) if sid else ("Normal", None)
    if ppr is not None:
        ol = ppr.find(W + "outlineLvl")
        if ol is not None:
            lvl = _outline_level(ol)
    m = HEADING_RE.match(name or "")
    if m:
        lvl = int(m.group(1))
    return name, lvl


def parse_clause(text):
    """Return (clause_id, title) from heading text. Unnumbered -> (None, text)."""
    t = SPLIT_NUM_RE.sub(r"\1.\2", norm_heading(text))
    a = ANNEX_RE.match(t)
    if a:
        title = re.sub(r"^\(?(normative|informative)\)?\s*:?\s*", "", a.group(2).strip(), flags=re.I)
        return a.group(1).upper(), title.strip() or t
    m = CLAUSE_RE.match(t)
    if m and (m.group(1)[0].isdigit() or "." in m.group(1)):
        return m.group(1), m.group(2).strip()
    # 38.331 IE/field headings "-<TAB>RRCReconfiguration": the dash is a list marker, not title text
    return None, re.sub(r"^[–\-]\s+", "", t)


def clause_level(clause, style_level):
    """Contract rule: a numbered clause's level is its number depth (A.1 -> 2, 5.3.5 -> 3),
    because 3GPP styles are inconsistent (annex A.1 uses Heading 1). Unnumbered -> style level."""
    return clause.count(".") + 1 if clause else style_level


def clause_parent(clause):
    return clause.rsplit(".", 1)[0] if clause and "." in clause else None


def is_equation_object(obj):
    ole = obj.find(".//" + O + "OLEObject")
    return ole is not None and (ole.get("ProgID") or "").startswith("Equation")


def iter_no_fallback(el, tag):
    """Like el.iter(tag) but skipping mc:Fallback subtrees."""
    for child in el:
        if child.tag == MC_FALLBACK:
            continue
        if child.tag == tag:
            yield child
        yield from iter_no_fallback(child, tag)


def basename(path):
    return path.replace("\\", "/").split("/")[-1]


def inspect(paths, n_samples):
    if isinstance(paths, str):
        paths = [paths]
    paths = sorted(paths, key=basename)
    report = {
        "source_file": basename(paths[0]),
        "source_files": [basename(p) for p in paths],
        "paragraph_styles": Counter(),
        "outline": [],
        "tables": {"body_level": 0, "with_merged_cells": 0, "nested": 0},
        "figures": {"drawing": 0, "vml_pict": 0, "ole_object": 0},
        "equations": 0,
        "equation_objects": 0,
        "track_changes": {"ins": 0, "del": 0},
        "asn1_start_markers": 0,
        "asn1_stop_markers": 0,
        "toc_fields": 0,
        "media_files": Counter(),
    }
    samples = defaultdict(list)
    order = 0
    for path in paths:
        order = _inspect_one(path, report, samples, n_samples, order)
    report["paragraph_styles"] = dict(report["paragraph_styles"].most_common())
    report["media_files"] = dict(report["media_files"])
    report["style_samples"] = dict(samples)
    return report


def _inspect_one(path, report, samples, n_samples, order):
    z = zipfile.ZipFile(path)
    styles = load_styles(z)
    src = basename(path)
    for name in z.namelist():
        if name.startswith("word/media/"):
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else "?"
            report["media_files"][ext] += 1

    depth = 0
    with z.open("word/document.xml") as f:
        for event, el in ET.iterparse(f, events=("start", "end")):
            if event == "start":
                depth += 1
                continue
            depth -= 1
            # depth 2 == direct children of w:body (document > body > child)
            if depth != 2:
                continue
            tag = el.tag
            if tag == W + "p":
                _handle_para(el, styles, report, samples, n_samples, order, src=src)
                order += 1
            elif tag == W + "tbl":
                report["tables"]["body_level"] += 1
                if el.find(".//" + W + "gridSpan") is not None or el.find(".//" + W + "vMerge") is not None:
                    report["tables"]["with_merged_cells"] += 1
                if el.find(".//" + W + "tc//" + W + "tbl") is not None:
                    report["tables"]["nested"] += 1
                for p in el.iter(W + "p"):
                    _handle_para(p, styles, report, samples, n_samples, order, in_table=True, src=src)
                order += 1
            el.clear()
    return order


def _handle_para(p, styles, report, samples, n_samples, order, in_table=False, src=None):
    name, lvl = para_style(p, styles)
    text = para_text(p)
    report["paragraph_styles"][name] += 1
    if len(samples[name]) < n_samples and text.strip():
        samples[name].append(text.strip()[:160])
    # mc:Fallback holds a VML copy of the mc:Choice DrawingML object: count it once (Choice only)
    report["figures"]["drawing"] += sum(1 for _ in iter_no_fallback(p, W + "drawing"))
    report["figures"]["vml_pict"] += sum(1 for _ in iter_no_fallback(p, W + "pict"))
    for obj in iter_no_fallback(p, W + "object"):  # OLE equations (Equation.3/DSMT) count as equations, not figures
        if is_equation_object(obj):
            report["equation_objects"] += 1
        else:
            report["figures"]["ole_object"] += 1
    report["equations"] += sum(1 for _ in p.iter(M + "oMath"))
    report["track_changes"]["ins"] += sum(1 for _ in p.iter(W + "ins"))
    report["track_changes"]["del"] += sum(1 for _ in p.iter(W + "del"))
    for instr in p.iter(W + "instrText"):
        if instr.text and instr.text.strip().upper().startswith("TOC"):
            report["toc_fields"] += 1
    if "ASN1START" in text:
        report["asn1_start_markers"] += 1
    if "ASN1STOP" in text:
        report["asn1_stop_markers"] += 1
    if lvl and not in_table and text.strip():
        clause, title = parse_clause(text)
        if ANNEX_RE.match(norm_heading(text)):
            level = 1  # 3GPP annex titles use Heading 8/9 but are top-level
        else:
            level = clause_level(clause, lvl)
        report["outline"].append({
            "order": order, "style": name, "style_level": lvl, "level": level,
            "clause": clause, "parent": clause_parent(clause), "title": title,
            "text": text.strip()[:200],
            "source_file": src,
        })


def print_summary(r):
    print(f"Source: {', '.join(r['source_files'])}")
    print(f"Headings: {len(r['outline'])}  (by level: "
          f"{dict(Counter(h['level'] for h in r['outline']))})")
    print(f"Tables: {r['tables']}")
    print(f"Figures: {r['figures']}  media: {r['media_files']}")
    print(f"Equations (OMML): {r['equations']}  OLE equations: {r['equation_objects']}  Track changes: {r['track_changes']}")
    print(f"ASN1START/STOP markers: {r['asn1_start_markers']}/{r['asn1_stop_markers']}  TOC fields: {r['toc_fields']}")
    print("\nParagraph styles (count):")
    for k, v in r["paragraph_styles"].items():
        print(f"  {v:7d}  {k}")
    print("\nOutline (first 40 headings):")
    for h in r["outline"][:40]:
        print(f"  {'  ' * (h['level'] - 1)}[{h['style']}] {h['clause'] or '-'} | {h['title'][:80]}")
    if r["style_samples"]:
        print("\nStyle samples:")
        for k, v in r["style_samples"].items():
            for s in v:
                print(f"  [{k}] {s}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docx", nargs="+", help="one .docx, or all parts of a multi-part spec")
    ap.add_argument("--json", help="write full report as JSON to this path")
    ap.add_argument("--samples", type=int, default=0, help="sample texts per style (default 0)")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):  # cp949 consoles cannot print Greek/symbols
        sys.stdout.reconfigure(errors="replace")
    try:
        r = inspect(a.docx, a.samples)
    except (zipfile.BadZipFile, KeyError) as e:
        print(f"ERROR: not a valid .docx ({e})", file=sys.stderr)
        sys.exit(2)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=1)
        print(f"wrote {a.json}")
    print_summary(r)


if __name__ == "__main__":
    main()
