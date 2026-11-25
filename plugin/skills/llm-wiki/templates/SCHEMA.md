# Wiki Schema

This file defines how this wiki is organized and maintained. Read it before every wiki task (ingest, query, lint). It was copied from the spec2md plugin template; the user and the LLM may change it together. When you change a rule here, also follow it in existing pages.

## 1. Layers and write access

The work folder holds three sibling folders:

```
work/
├── raw/      # clause Markdown converted from 3GPP .docx (faithful to the original)
├── linked/   # copy of raw/ with cross-reference links, <a id> anchors and "Referenced by" sections
└── wiki/     # this wiki
```

| Layer | Folder | Write access |
| --- | --- | --- |
| Raw sources | `raw/` (original conversion) and `linked/` (linked copy). Cite `linked/`, never `raw/` | Read only. Never edit |
| Wiki | `wiki/` | Written by the LLM |
| Schema | `wiki/SCHEMA.md` (this file) | Changed only by agreement with the user |

The wiki summarizes, connects and explains. Fidelity to the original text is the job of `linked/`, so the wiki links to it instead of copying it.

## 2. Folders and file names

```
wiki/
├── SCHEMA.md    # this file
├── index.md     # every page: link + one-line summary + specs and source count, grouped by type
├── log.md       # append-only work log
├── features/    # features that span specs (beam-failure-recovery.md)
├── concepts/    # IEs, timers, channels, terms (t310.md, pdcch.md)
├── specs/       # one summary page per spec: scope, chapter layout, main topics (38.321.md)
└── answers/     # query answers kept as pages
```

- File names are lowercase kebab-case English: `features/beam-failure-recovery.md`, `concepts/beamfailurerecoveryconfig.md`.
- Spec pages are named by spec number: `specs/38.321.md`.
- Keep a page's file name stable once it exists. Other pages link to it.

## 3. Page front matter

Every page starts with a front matter block. Each value is a one-line scalar or a one-line JSON array (no multi-line YAML; the block is read without a YAML library).

```
---
type: feature
title: Beam Failure Recovery
sources: ["linked/38321-j40/clauses/0075_5.17_beam-failure-detection-and-recovery-procedure.md", "linked/38321-j40/clauses/0286_7.1_rnti-values.md#table-7.1-1"]
specs: ["TS 38.321 19.4.0"]
related: ["concepts/beamfailurerecoveryconfig.md"]
updated: 2026-11-26
---
```

| Key | Required | Value |
| --- | --- | --- |
| `type` | yes | `feature`, `concept`, `spec` or `answer` (matches the folder) |
| `title` | yes | Page title, plain one-line text |
| `sources` | yes | Non-empty JSON array of every `linked/` file the body cites, as paths relative to the work folder (`linked/{spec}/clauses/{file}.md`, optionally with `#anchor`). Do not repeat a path |
| `specs` | yes | JSON array of the specs cited, each `"TS 38.321 19.4.0"` (spec number and version from the clause file's front matter) |
| `related` | no | JSON array of related wiki pages, as paths relative to `wiki/` (`"concepts/t310.md"`). `[]` if none |
| `updated` | yes | Date of the last change, `YYYY-MM-DD` |

## 4. Sources and links

**Every statement needs a source.** Each prose sentence (or each list item) carries at least one link to the `linked/` clause it comes from. If you cannot find a source, do not write the statement.

**Link format.** Use standard Markdown relative links from the page's own folder. `wiki/` and `linked/` are siblings, so a page in `wiki/features/` reaches `linked/` with `../../linked/`:

```
The MAC entity counts beam failure instances indicated by the lower layers ([TS 38.321 §5.17](../../linked/38321-j40/clauses/0075_5.17_beam-failure-detection-and-recovery-procedure.md)).
The RNTI values are listed in [TS 38.321 Table 7.1-1](../../linked/38321-j40/clauses/0286_7.1_rnti-values.md#table-7.1-1).
```

Links between wiki pages are relative too: from `features/x.md` use `../concepts/t310.md`; from `index.md` use `features/x.md`.

**Anchors.** Link to the most specific target:

- A table, figure or sub-clause inside a file: use the `<a id>` anchors that `linked/` puts before them — `#table-7.1-1`, `#figure-5.3.5-1`, `#clause-5.2.2.2.1`.
- A clause that starts its own file: link the file with no anchor.
- Avoid heading slugs (`#5171-general`). The lint script accepts them, but they break when a heading changes in a new release; `<a id>` anchors follow the clause number.

The lint script checks that every link target file exists and that every `#anchor` exists in it. After a reconversion, broken source links show up as lint ERRORs; find the clause in the new `linked/` and fix the link.

**Do not copy tables or equations.** Link them and say in one sentence what they define. Short quoted terms (an IE or field name, a timer name) are fine.

**Cite where the content is.** `linked/` files end with a `## Referenced by` section that lists the clauses pointing at them. Use it to find related clauses, but cite the clause that actually says the thing.

## 5. Conflicts

If two specs or clauses appear to disagree, do not delete either side and do not silently pick one. Keep both in a CONFLICT block, each side with its source:

```
> CONFLICT: TS 38.321 §5.17 says <statement A> ([TS 38.321 §5.17](../../linked/38321-j40/clauses/0075_5.17_beam-failure-detection-and-recovery-procedure.md)), while TS 38.331 says <statement B> ([TS 38.331 BeamFailureRecoveryConfig](../../linked/38331-j40/clauses/0586_beamfailurerecoveryconfig.md)). <Likely cause, only if a source supports it.> Not resolved.
```

Start the block with `> CONFLICT:` and keep it on one blockquote line or a few `>` lines. Add a short note on the likely cause (different release, different scope, editorial error) only if a source supports it. Remove a CONFLICT block only when a source resolves it, and say so in `log.md`.

## 6. Page bodies

After the front matter, start with `# {title}`. Suggested sections (omit the ones that have no sourced content):

| Type | Sections |
| --- | --- |
| feature | Summary, Specs involved, Procedure, Configuration, Related |
| concept | Definition, Where it is used, Related |
| spec | Scope, Structure (chapters), Main topics, Related |
| answer | Question, Answer, Sources |

- Write in English. Describe; do not speculate beyond the sources.
- Each page links to at least one other wiki page (usually under "Related") and is linked from at least one. A page with no incoming link from another page is reported as an orphan.
- Prefer short paragraphs and lists, each with its source links. The lint script warns when a page has 5 or more body paragraphs without a link into `linked/`.

## 7. index.md

`index.md` lists every page, grouped by type in this order. Each line: link, an em dash, a one-line summary, then the spec numbers and the number of entries in `sources`.

```
# Wiki Index

## Features
- [Beam Failure Recovery](features/beam-failure-recovery.md) — How the UE detects beam failure and recovers (specs: 38.321, 38.331; sources: 7)

## Concepts
- [BeamFailureRecoveryConfig](concepts/beamfailurerecoveryconfig.md) — RRC IE that configures beam failure recovery (specs: 38.331; sources: 1)

## Specs

## Answers
```

Keep lines sorted by title within a group. Every page must appear here; the lint script reports a page missing from the index as an ERROR.

## 8. log.md

`log.md` is append-only. Each entry starts with a heading line of exactly this form, followed by short bullet lines:

```
# Wiki Log

## [2026-11-26] ingest | 38.321 beam-failure-recovery
- created features/beam-failure-recovery.md
- updated concepts/beamfailurerecoveryconfig.md

## [2026-11-26] query | how is beam failure recovery triggered
- saved answers/how-is-beam-failure-recovery-triggered.md

## [2026-11-26] lint | 0 errors, 1 warning
- fixed 2 broken source links after reconversion
```

The operation is one of `ingest`, `query`, `lint`. Never edit or delete past entries.

## 9. Procedures

**ingest** (unit: one topic of one spec, `raw/{spec}/topics/{id}.md`)
1. If the spec has no `raw/{spec}/topics/topics.json`, group its clauses into topics first.
2. Read the topic file. Each clause in it is preceded by `<!-- source: clauses/{file}.md -->`; the citable copy is `linked/{spec}/clauses/{file}.md`. Follow the topic clauses' outgoing references (`linked/{spec}/refs.json`, rows with `status: resolved`) and incoming references (the `## Referenced by` section of each clause file) one hop to find related clauses in other specs.
3. Report the key points to the user and agree on the direction (unless the user asked for a batch run).
4. Create or update the feature, concept and spec pages; update `index.md`; append a `log.md` entry; run lint.

**query**
1. Read this file, then `index.md`, then the relevant pages, then the `linked/` clauses they cite.
2. If the wiki has nothing or too little, search `linked/` directly and widen through `refs.json` and `## Referenced by` (for example, collect every clause that references a table the question is about).
3. Answer in the user's language with source links. Say which parts come from the wiki and which were found directly in `linked/`.
4. If the answer is worth keeping, ask the user, then save it under `answers/` and update `index.md` and `log.md`.

**lint**
1. Run the lint script and fix every ERROR (broken links or anchors, missing or malformed front matter, empty `sources`, pages missing from `index.md`, malformed `log.md` entries).
2. Review WARNs (orphan pages, paragraphs without sources) and fix them where possible.
3. Check what the script cannot: contradictions between pages, concepts mentioned without a page, missing cross-links, topics worth ingesting next. Report them.
4. Append a `lint` entry to `log.md`.

At the end of every task, `index.md` and `log.md` are up to date and the lint script reports 0 errors.
