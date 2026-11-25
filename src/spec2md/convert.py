"""Convert one spec (one .docx or all parts of a multi-part spec) to raw/{code}/."""
import json
import os
import shutil
import sys
import time
from collections import Counter

from . import __version__
from .blocks import MediaStore, Renderer, paragraph_block, style_kind, table_block
from .headings import Heading, clause_parent, heading_text, para_style
from .ns import M, W, local
from .reader import Part, basename, find_cover_version, split_name, version_from_code
from .split import Section, file_name, front_matter, plan, totals

SKIP_TITLES = {"contents", "table of contents"}
BODY_IGNORE = {"sectPr", "bookmarkStart", "bookmarkEnd", "proofErr", "permStart", "permEnd",
               "commentRangeStart", "commentRangeEnd", "moveFromRangeStart", "moveFromRangeEnd",
               "moveToRangeStart", "moveToRangeEnd"}


def log(msg):
    print(msg, file=sys.stderr, flush=True)


class ConversionError(Exception):
    pass


def group_paths(paths):
    """Sort parts by file name and check they belong to one spec code."""
    paths = sorted(paths, key=basename)
    codes = {split_name(p)[0] for p in paths}
    if len(codes) != 1:
        raise ConversionError(f"files belong to different spec codes: {sorted(codes)}")
    return codes.pop(), paths


class SpecConverter:
    def __init__(self, paths, out_root, split_depth=3, max_chars=60000, quiet=False):
        self.code, self.paths = group_paths(paths)
        self.out = os.path.join(out_root, self.code)
        self.depth = split_depth
        self.max_chars = max_chars
        self.quiet = quiet
        self.skipped = []
        self.entries = []
        self.order = 0
        self.stack = []
        self.unit = []
        self.current = None
        self.warnings = []
        self.files = 0
        self.multi = any(split_name(p)[1] for p in self.paths)

    # ------------------------------------------------------------------
    def _log(self, msg):
        if not self.quiet:
            log(msg)

    def _skip(self, part, what):
        label = f"{part.part}: {what}" if part.part else what
        if label not in self.skipped:
            self.skipped.append(label)

    def _prepare_out(self):
        os.makedirs(self.out, exist_ok=True)
        for sub in ("clauses", "media"):
            p = os.path.join(self.out, sub)
            if os.path.isdir(p):
                shutil.rmtree(p)
        os.makedirs(os.path.join(self.out, "clauses"))
        mp = os.path.join(self.out, "manifest.json")
        if os.path.exists(mp):
            os.remove(mp)

    def _metadata(self, parts):
        number, version = version_from_code(self.code)
        kind = "TS"
        ordered = sorted(parts, key=lambda p: (0 if (p.part and "cover" in p.part.lower()) else 1))
        cover = None
        for p in ordered:
            cover = find_cover_version(p)
            if cover:
                break
        if cover:
            ckind, cnum, cver = cover
            if (number and cnum != number) or (version and cver != version):
                self.warnings.append(
                    f"cover says {ckind} {cnum} V{cver} but file name says {number} V{version}; using cover")
            kind, number, version = ckind, cnum, cver
        if not number:
            number = self.code
        if not version:
            self.warnings.append("version not found in file name or cover")
            version = "unknown"
        release = f"Rel-{version.split('.')[0]}" if version[0].isdigit() else "unknown"
        return {"spec": f"{kind} {number}", "spec_number": number, "version": version, "release": release}

    # ------------------------------------------------------------------
    def run(self):
        t0 = time.time()
        parts = [Part(p) for p in self.paths]
        try:
            self.meta = self._metadata(parts)
            self._prepare_out()
            self.renderer = Renderer(MediaStore(os.path.join(self.out, "media")))
            for i, part in enumerate(parts):
                self._log(f"[{self.code}] part {i + 1}/{len(parts)}: {part.name}")
                self.renderer.part = part
                self._convert_part(part, first=(i == 0))
            self._flush_unit()
        finally:
            for p in parts:
                p.close()
        manifest = {
            "spec": self.meta["spec"], "spec_number": self.meta["spec_number"],
            "version": self.meta["version"], "release": self.meta["release"],
            "source_files": [basename(p) for p in self.paths],
            "tool_version": __version__,
            "split_depth": self.depth,
            "max_chars": self.max_chars,
            "skipped": self.skipped,
            "ole_equations": {"latex": self.renderer.ole_stats["latex"],
                              "image_only": self.renderer.ole_stats["image_only"]},
            "clauses": self.entries,
        }
        with open(os.path.join(self.out, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
            f.write("\n")
        elapsed = time.time() - t0
        self.summary = {
            "code": self.code, "entries": len(self.entries), "files": self.files,
            "media": sum(1 for v in self.renderer.media.done.values() if v),
            "seconds": round(elapsed, 1),
            "unhandled_styles": dict(sorted(self.renderer.unhandled_styles.items())),
            "unhandled_elements": dict(sorted(self.renderer.unhandled_elements.items())),
            "unhandled_math": dict(sorted(self.renderer.omml.unhandled.items())),
            "unmapped_symbols": dict(sorted(self.renderer.unmapped_symbols.items())),
            "notes": dict(sorted(self.renderer.notes.items())),
            "ole_equations": dict(self.renderer.ole_stats),
            "ole_equation_failures": dict(sorted(self.renderer.ole_failures.items())),
            "warnings": self.warnings,
        }
        self._report()
        return self.summary

    def _report(self):
        s = self.summary
        self._log(f"[{self.code}] {s['entries']} manifest entries, {s['files']} files, "
                  f"{s['media']} media, {s['seconds']}s -> {self.out}")
        ole = s["ole_equations"]
        if ole["latex"] or ole["image_only"]:
            self._log(f"[{self.code}] OLE equations: {ole['latex']} LaTeX, {ole['image_only']} image only")
        for w in s["warnings"]:
            log(f"WARNING [{self.code}] {w}")
        for key in ("unhandled_styles", "unhandled_elements", "unhandled_math", "unmapped_symbols",
                    "notes", "ole_equation_failures"):
            if s[key]:
                log(f"WARNING [{self.code}] {key.replace('_', ' ')}: {json.dumps(s[key], ensure_ascii=False)}")

    # ------------------------------------------------------------------
    def _body_nodes(self, el):
        """Body child -> nodes to process (w:sdt / w:customXml are wrappers)."""
        if el.tag == W + "sdt":
            content = el.find(W + "sdtContent")
            if content is not None:
                for c in content:
                    yield from self._body_nodes(c)
        elif el.tag == W + "customXml":
            for c in el:
                yield from self._body_nodes(c)
        else:
            yield el

    def _convert_part(self, part, first):
        r = self.renderer
        pre = Section(None)       # content before this part's first heading
        pre_seen = False          # any element before the first heading
        cover_marks = False       # cover/TOC styles seen before the first heading
        seen_heading = False
        in_contents = False       # inside a 'Contents' heading's section

        def resolve_pre():
            nonlocal pre
            if not pre_seen:
                return
            if first or cover_marks or self.current is None:
                self._skip(part, "cover")
            else:
                self.current.absorb(pre)
            pre = Section(None)

        for el in part.iter_body():
            for node in self._body_nodes(el):
                tag = node.tag
                if tag == W + "p":
                    name, lvl = para_style(node, part.styles)
                    if lvl:
                        text = heading_text(node)
                        if text.strip():
                            if not seen_heading:
                                resolve_pre()
                                seen_heading = True
                            h = Heading(text, name, lvl, part.name)
                            if h.title.strip().lower() in SKIP_TITLES:
                                in_contents = True
                                self._skip(part, "contents")
                                continue
                            in_contents = False
                            h.equations = sum(1 for _ in node.iter(M + "oMath"))
                            self._start_heading(h)
                            continue
                    kind = style_kind(name)
                    if kind == "toc":
                        self._skip(part, "contents")
                        if not seen_heading:
                            cover_marks = True
                        continue
                    if kind == "cover":
                        self._skip(part, "cover")
                        if not seen_heading:
                            cover_marks = True
                        continue
                    if in_contents:
                        continue
                    if not seen_heading:
                        pre_seen = True
                        if first:
                            self._skip(part, "cover")
                    # the first part's pre-heading content is always the cover: do not render it
                    target = self.current if seen_heading else (None if first else pre)
                    if target is None:
                        continue
                    k, text, res = paragraph_block(r, node, name)
                    if k == "code":
                        target.add_code(text)
                        target.count(res.figures, res.equations)
                    elif k == "md":
                        target.add(text, figures=res.figures, equations=res.equations)
                    else:
                        target.add("", figures=res.figures, equations=res.equations)
                elif tag == W + "tbl":
                    if in_contents:
                        continue
                    if not seen_heading:
                        pre_seen = True
                        if first:
                            self._skip(part, "cover")
                        if any(style_kind(part.style_name(ps.get(W + "val"))) in ("cover", "toc")
                               for ps in node.iter(W + "pStyle")):
                            cover_marks = True
                    target = self.current if seen_heading else (None if first else pre)
                    if target is None:
                        continue
                    tr = table_block(r, node)
                    target.add(tr.text, tables=1, figures=tr.figures, equations=tr.equations)
                elif local(tag) in BODY_IGNORE and tag.startswith(W):
                    continue
                else:
                    r.unhandled_elements["body " + local(tag)] += 1
        if not seen_heading:
            resolve_pre()

    # ------------------------------------------------------------------
    def _start_heading(self, h):
        while self.stack and self.stack[-1].level >= h.level:
            self.stack.pop()
        if h.clause:
            h.parent = clause_parent(h.clause)
        else:
            h.parent = self.stack[-1].key if self.stack else None
        h.path = [x.display for x in self.stack] + [h.display]
        self.stack.append(h)
        sec = Section(h)
        sec.equations += h.equations
        if self.current is not None:
            self.current.close_code()
        if h.level <= self.depth or not self.unit:
            self._flush_unit()
            self.unit = [sec]
        else:
            self.unit.append(sec)
        self.current = sec

    def _flush_unit(self):
        if not self.unit:
            return
        for s in self.unit:
            s.close_code()
        for secs, auto, body in plan(self.unit, self.max_chars):
            self.order += 1
            h = secs[0].heading
            entry = {"order": self.order, "clause": h.key, "title": h.title, "level": h.level,
                     "parent": h.parent, "source_file": h.source_file, "file": None}
            counts = totals(secs) if body is not None else {
                "tables": 0, "figures": 0, "code_blocks": 0, "equations": 0}
            if body is not None:
                rel = "clauses/" + file_name(self.order, h)
                with open(os.path.join(self.out, rel), "w", encoding="utf-8", newline="\n") as f:
                    f.write(front_matter(self.meta, h))
                    f.write(body)
                entry["file"] = rel
                self.files += 1
            entry.update(counts)
            entry["chars"] = len(body) if body is not None else 0
            if auto:
                entry["auto_split"] = True
            self.entries.append(entry)
        self.unit = []
