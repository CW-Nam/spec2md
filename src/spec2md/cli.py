"""Command line: convert / batch / topics."""
import argparse
import glob
import os
import sys
import traceback

from .convert import ConversionError, SpecConverter, log
from .reader import basename, spec_code


def _depth_overrides(items):
    out = {}
    for it in items or []:
        code, _, n = it.partition("=")
        if not n.isdigit():
            raise SystemExit(f"--depth expects CODE=N, got {it!r}")
        out[code] = int(n)
    return out


def cmd_convert(a):
    try:
        conv = SpecConverter(a.docx, a.out, split_depth=a.split_depth, max_chars=a.max_chars)
        conv.run()
    except ConversionError as e:
        log(f"ERROR: {e}")
        return 2
    return 0


def group_dir(spec_dir):
    docs = sorted(glob.glob(os.path.join(spec_dir, "*.docx")), key=basename)
    docs = [d for d in docs if not basename(d).startswith("~$")]  # Word lock files
    groups = {}
    for d in docs:
        groups.setdefault(spec_code(d), []).append(d)
    return dict(sorted(groups.items()))


def cmd_batch(a):
    overrides = _depth_overrides(a.depth)
    groups = group_dir(a.specs)
    if a.only:
        want = set(a.only.split(","))
        groups = {c: g for c, g in groups.items() if c in want}
    if not groups:
        log(f"no .docx files in {a.specs}")
        return 1
    failed = []
    for code, parts in groups.items():
        depth = overrides.get(code, a.split_depth)
        log(f"=== {code} ({len(parts)} file(s), split depth {depth})")
        try:
            SpecConverter(parts, a.out, split_depth=depth, max_chars=a.max_chars).run()
        except Exception as e:  # keep going; report at the end
            failed.append((code, f"{type(e).__name__}: {e}"))
            log(traceback.format_exc())
    log(f"\nbatch: {len(groups) - len(failed)}/{len(groups)} converted")
    for code, why in failed:
        log(f"FAILED {code}: {why}")
    return 1 if failed else 0


def cmd_topics(a):
    from .topics import build_topics
    try:
        n = build_topics(a.spec_dir)
    except (OSError, ValueError, KeyError) as e:
        log(f"ERROR: {e}")
        return 2
    log(f"wrote {n} topic files to {os.path.join(a.spec_dir, 'topics')}")
    return 0


def main(argv=None):
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(prog="spec2md", description="3GPP .docx -> clause-level Markdown raw files")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("convert", help="convert one spec (all parts of a multi-part spec)")
    c.add_argument("docx", nargs="+")
    c.add_argument("-o", "--out", default="raw")
    c.add_argument("--split-depth", type=int, default=3)
    c.add_argument("--max-chars", type=int, default=60000)
    c.set_defaults(fn=cmd_convert)

    b = sub.add_parser("batch", help="convert every spec in a directory")
    b.add_argument("specs")
    b.add_argument("-o", "--out", default="raw")
    b.add_argument("--split-depth", type=int, default=3)
    b.add_argument("--max-chars", type=int, default=60000)
    b.add_argument("--depth", action="append", metavar="CODE=N",
                   help="per-spec split depth, e.g. --depth 38331-j40=4 (repeatable)")
    b.add_argument("--only", help="comma-separated spec codes")
    b.set_defaults(fn=cmd_batch)

    t = sub.add_parser("topics", help="build topic files from topics/topics.json")
    t.add_argument("spec_dir")
    t.set_defaults(fn=cmd_topics)

    a = ap.parse_args(argv)
    return a.fn(a)
