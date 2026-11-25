"""Sections, split units, --max-chars recursion, file names and front matter."""
import json

from .headings import slugify


class Section:
    """One heading and the Markdown blocks up to the next heading."""

    __slots__ = ("heading", "blocks", "code", "tables", "figures", "code_blocks", "equations")

    def __init__(self, heading):
        self.heading = heading
        self.blocks = []
        self.code = None
        self.tables = self.figures = self.code_blocks = self.equations = 0

    @property
    def level(self):
        return self.heading.level

    def add(self, text, tables=0, figures=0, equations=0):
        self.close_code()
        if text:
            self.blocks.append(text)
        self.tables += tables
        self.figures += figures
        self.equations += equations

    def count(self, figures=0, equations=0):
        self.figures += figures
        self.equations += equations

    def add_code(self, line):
        if self.code is None:
            self.code = []
        self.code.append(line)

    def close_code(self):
        if self.code is None:
            return
        lines = "\n".join(self.code).split("\n")
        self.code = None
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            return
        lang = "asn1" if any("::=" in ln or "ASN1START" in ln for ln in lines) else "text"
        self.blocks.append("```" + lang + "\n" + "\n".join(lines) + "\n```")
        self.code_blocks += 1

    def absorb(self, other):
        """Append another section's blocks and counts (pre-heading content of a later part)."""
        self.close_code()
        other.close_code()
        self.blocks.extend(other.blocks)
        self.tables += other.tables
        self.figures += other.figures
        self.code_blocks += other.code_blocks
        self.equations += other.equations

    def empty(self):
        return not self.blocks and self.code is None


def render_body(secs):
    head = secs[0].heading
    out = ["# " + head.display]
    out.extend(secs[0].blocks)
    for s in secs[1:]:
        n = min(6, max(2, 1 + s.heading.level - head.level))
        out.append("#" * n + " " + s.heading.display)
        out.extend(s.blocks)
    return "\n\n".join(out) + "\n"


def plan(secs, max_chars, auto=False):
    """Split a unit into files: [(sections, auto_split, body or None)].

    A file whose body exceeds ``max_chars`` and that holds deeper headings is
    split at its shallowest sub-heading level, recursively. A section with no
    content and no sub-headings in the file gets body None (manifest file null).
    """
    if len(secs) == 1:
        body = None if secs[0].empty() else render_body(secs)
        return [(secs, auto, body)]
    body = render_body(secs)
    if max_chars is None or len(body) <= max_chars:
        return [(secs, auto, body)]
    m = min(s.level for s in secs[1:])
    idx = [i for i in range(1, len(secs)) if secs[i].level == m]
    head = secs[:idx[0]]
    out = plan(head, max_chars, auto) if len(head) > 1 else [
        (head, auto, None if head[0].empty() else render_body(head))]
    for a, b in zip(idx, idx[1:] + [len(secs)]):
        out.extend(plan(secs[a:b], max_chars, True))
    return out


def file_name(order, heading):
    slug = slugify(heading.title)[:60].strip("-") or "untitled"
    if heading.clause:
        return f"{order:04d}_{heading.clause}_{slug}.md"
    return f"{order:04d}_{slug}.md"


def _q(v):
    return json.dumps(v, ensure_ascii=False)


def front_matter(meta, heading):
    lines = [
        "---",
        f"spec: {_q(meta['spec'])}",
        f"spec_number: {_q(meta['spec_number'])}",
        f"version: {_q(meta['version'])}",
        f"release: {_q(meta['release'])}",
        f"clause: {_q(heading.key)}",
        f"title: {_q(heading.title)}",
        f"level: {heading.level}",
        f"parent: {_q(heading.parent) if heading.parent else 'null'}",
        f"path: {_q(heading.path)}",
        f"source_file: {_q(heading.source_file)}",
        "---",
    ]
    return "\n".join(lines) + "\n"


def totals(secs):
    return {k: sum(getattr(s, k) for s in secs) for k in ("tables", "figures", "code_blocks", "equations")}
