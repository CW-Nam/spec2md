#!/usr/bin/env python3
"""Run inspect_docx.py + check_output.py for every spec in a directory (stdlib only).

Usage:
  python check_all.py --specs specs --raw raw --ws _workspace [--phase 03] [--only 38331-i10,38300-i00]

Spec code = docx stem, minus a multi-part suffix (output-contract.md section 1):
  36101-j60_s00-07.docx -> 36101-j60. All parts of one code are inspected together.

For each spec code:
  1. _workspace/01_inspect_{code}.json  (created if missing or older than any part or inspect_docx.py)
  2. check_output.py --out raw/{code} --json _workspace/{phase}_checker_{code}.json
Writes _workspace/{phase}_check_summary.json and prints a table.
Exit 0 if all PASS, 1 if any FAIL/missing output.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.dirname(os.path.dirname(HERE))
INSPECT = os.path.join(SKILLS, "3gpp-docx-structure", "scripts", "inspect_docx.py")
CHECK = os.path.join(SKILLS, "conversion-check", "scripts", "check_output.py")
PART_RE = re.compile(r"^(\d{5}(?:-\d+)?-[0-9a-z]\d{2})_(.+)$")
NUM_PART_RE = re.compile(r"^(\d{5}(?:-\d+)?-[0-9a-z]\d{2}_)(\d+)(?=_)")


def part_sort_key(path):
    """File-name order, but a numeric part prefix ('38133-j60_10_sA06...') sorts as a number."""
    return NUM_PART_RE.sub(lambda m: m.group(1) + m.group(2).zfill(9), os.path.basename(path))


def spec_code(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    m = PART_RE.match(stem)
    return m.group(1) if m else stem


def group_specs(docs):
    groups = {}
    for d in sorted(docs, key=part_sort_key):
        groups.setdefault(spec_code(d), []).append(d)
    return dict(sorted(groups.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--specs", default="3gpp-specs")
    ap.add_argument("--raw", default="raw")
    ap.add_argument("--ws", default="_workspace")
    ap.add_argument("--phase", default="03")
    ap.add_argument("--only", help="comma-separated spec codes")
    a = ap.parse_args()
    os.makedirs(a.ws, exist_ok=True)
    docs = sorted(glob.glob(os.path.join(a.specs, "*.docx")))
    docs = [d for d in docs if not os.path.basename(d).startswith("~$")]  # Word lock files
    groups = group_specs(docs)
    if a.only:
        want = set(a.only.split(","))
        groups = {c: g for c, g in groups.items() if c in want}
    rows = []
    for code, parts in groups.items():
        ij = os.path.join(a.ws, f"01_inspect_{code}.json")
        row = {"spec": code, "parts": len(parts), "status": None, "errors": None, "warnings": None,
               "report": None}
        if not os.path.exists(ij) or os.path.getmtime(ij) < max(os.path.getmtime(d) for d in [*parts, INSPECT]):
            r = subprocess.run([sys.executable, INSPECT, *parts, "--json", ij], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            if r.returncode != 0:
                row.update(status="INSPECT_FAIL", detail=r.stderr.strip()[-500:])
                rows.append(row)
                continue
        out = os.path.join(a.raw, code)
        if not os.path.exists(os.path.join(out, "manifest.json")):
            row.update(status="NO_OUTPUT")
            rows.append(row)
            continue
        rj = os.path.join(a.ws, f"{a.phase}_checker_{code}.json")
        r = subprocess.run([sys.executable, CHECK, "--inspect", ij, "--out", out, "--json", rj],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        if r.returncode == 2 or not os.path.exists(rj):
            row.update(status="CHECK_ERROR", detail=(r.stderr or r.stdout).strip()[-500:])
        else:
            rep = json.load(open(rj, encoding="utf-8"))
            row.update(status="PASS" if rep["ok"] else "FAIL", errors=len(rep["errors"]),
                       warnings=len(rep["warnings"]), report=rj)
        rows.append(row)
    summary = os.path.join(a.ws, f"{a.phase}_check_summary.json")
    json.dump(rows, open(summary, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{'spec':<20} {'status':<13} {'err':>4} {'warn':>5}")
    for r in rows:
        e = "-" if r["errors"] is None else r["errors"]
        w = "-" if r["warnings"] is None else r["warnings"]
        print(f"{r['spec']:<20} {r['status']:<13} {e!s:>4} {w!s:>5}")
    bad = [r for r in rows if r["status"] != "PASS"]
    print(f"\n{len(rows) - len(bad)}/{len(rows)} PASS. summary: {summary}")
    if not rows:
        print("no .docx files found", file=sys.stderr)
    sys.exit(0 if rows and not bad else 1)


if __name__ == "__main__":
    main()
