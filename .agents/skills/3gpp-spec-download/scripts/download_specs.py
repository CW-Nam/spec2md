"""Download Word documents from 3GPP's latest specification directories."""

import argparse
from html.parser import HTMLParser
from http.client import HTTPException
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
from tempfile import TemporaryDirectory, TemporaryFile
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile


LATEST = "https://www.3gpp.org/ftp/Specs/latest/"
DEFAULT_LIST = Path(__file__).resolve().parents[1] / "specs.txt"
DEFAULT_DIRECTORY = Path.home() / "3gpp-specs"
WORD_EXTENSIONS = {".doc", ".docx"}
SPEC = r"[0-9]{5}(?:-[0-9]+)*"
ARCHIVE_NAME = re.compile(rf"({SPEC})-([0-9a-z]{{3}})\.zip", re.IGNORECASE)
LOCAL_NAME = re.compile(rf"({SPEC})-[0-9a-z]{{3}}(?:_|$)", re.IGNORECASE)
TIMEOUT = 30
HEADERS = {"User-Agent": "3gpp-spec-download/1.0"}


def display_number(spec):
    return f"{spec[:2]}.{spec[2:]}"


def load_specs(path):
    specs = set()
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        value = line.partition("#")[0].strip()
        if not value:
            continue
        if not re.fullmatch(r"[0-9]{2}\.?[0-9]{3}(?:-[0-9]+)*", value):
            raise ValueError(f"{path}:{number}: invalid specification number {value!r}")
        specs.add(value.replace(".", ""))
    if not specs:
        raise ValueError(f"{path}: no specification numbers found")
    return sorted(specs)


def save_list(source, target):
    specs = set()
    for path in source.iterdir():
        if path.suffix.lower() in WORD_EXTENSIONS | {".zip"} and path.is_file():
            match = LOCAL_NAME.match(path.stem)
            if match:
                specs.add(match[1])
    if not specs:
        raise ValueError(f"{source}: no specification files found")

    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=target.parent) as scratch:
        draft = Path(scratch) / "specs.txt"
        draft.write_text("".join(f"{display_number(spec)}\n" for spec in sorted(specs)), encoding="utf-8")
        draft.replace(target)
    print(f"Saved {len(specs)} specifications to {target}")


class DirectoryLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.extend(value for key, value in attrs if key == "href" and value)


def latest_archives(release, series):
    directory = f"{LATEST}{release}/{series}_series/"
    expected = urlsplit(directory)
    links = DirectoryLinks()
    with urlopen(Request(directory, headers=HEADERS), timeout=TIMEOUT) as response:
        links.feed(response.read().decode(response.headers.get_content_charset() or "utf-8"))
    links.close()

    candidates = {}
    for href in links.hrefs:
        url = urljoin(directory, href)
        link = urlsplit(url)
        folder, _, filename = link.path.rpartition("/")
        if (link.scheme, link.netloc, folder + "/") != (expected.scheme, expected.netloc, expected.path):
            continue
        match = ARCHIVE_NAME.fullmatch(filename)
        if match:
            spec, version = match.groups()
            candidate = (version.lower(), url)
            if spec not in candidates or candidate > candidates[spec]:
                candidates[spec] = candidate
    return {spec: url for spec, (_, url) in candidates.items()}


def unpack_documents(url, output):
    with TemporaryFile() as archive:
        with urlopen(Request(url, headers=HEADERS), timeout=TIMEOUT) as response:
            shutil.copyfileobj(response, archive)
        archive.seek(0)
        with ZipFile(archive) as zipped:
            documents = {}
            for member in zipped.infolist():
                name = PurePosixPath(member.filename.replace("\\", "/")).name
                if member.is_dir() or Path(name).suffix.lower() not in WORD_EXTENSIONS:
                    continue
                if re.search(r'[<>:"|?*\x00-\x1f]', name) or name.casefold() in documents:
                    raise ValueError(f"Invalid or duplicate Word filename in ZIP: {name!r}")
                documents[name.casefold()] = (name, member)
            if not documents:
                raise ValueError("The ZIP contains no Word documents")

            output.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(dir=output, prefix=".3gpp-") as scratch:
                saved = skipped = 0
                staged = []
                for name, member in documents.values():
                    target = output / name
                    if target.is_file():
                        skipped += 1
                        continue
                    draft = Path(scratch) / name
                    with zipped.open(member) as source, draft.open("xb") as destination:
                        shutil.copyfileobj(source, destination)
                    staged.append((draft, target))
                for draft, target in staged:
                    try:
                        if os.name == "nt":
                            draft.rename(target)
                        else:
                            os.link(draft, target)
                    except FileExistsError:
                        if not target.is_file():
                            raise
                        skipped += 1
                    else:
                        saved += 1
    return saved, skipped


def download(specs, release, output, dry_run):
    listings = {}
    failed = 0
    for spec in specs:
        series = spec[:2]
        number = display_number(spec)
        if series not in listings:
            try:
                listings[series] = latest_archives(release, series)
            except (OSError, HTTPException, ValueError) as error:
                listings[series] = error
        listing = listings[series]
        if isinstance(listing, Exception):
            print(f"{number}: unable to read {release}/{series}_series/: {listing}", file=sys.stderr)
            failed += 1
            continue
        if spec not in listing:
            print(f"{number}: no ZIP listed in {release}", file=sys.stderr)
            failed += 1
            continue
        url = listing[spec]
        if dry_run:
            print(f"{number}: {url}")
            continue
        try:
            saved, skipped = unpack_documents(url, output)
        except (OSError, HTTPException, BadZipFile, RuntimeError, ValueError) as error:
            print(f"{number}: {url}: {error}", file=sys.stderr)
            failed += 1
            continue
        print(f"{number}: {url.rsplit('/', 1)[-1]}, {saved} saved, {skipped} already present")
    return int(failed > 0)


def release_name(value):
    match = re.fullmatch(r"(?:Rel-)?([1-9][0-9]*)", value, re.IGNORECASE)
    if not match:
        raise argparse.ArgumentTypeError("use a release such as Rel-19 or 19")
    return f"Rel-{match[1]}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("download", help="download the latest Word documents for a saved list")
    fetch.add_argument("--list", type=Path, default=DEFAULT_LIST)
    fetch.add_argument("--release", type=release_name, default="Rel-19")
    fetch.add_argument("--output", type=Path, default=DEFAULT_DIRECTORY)
    fetch.add_argument("--dry-run", action="store_true", help="look up ZIP URLs without saving files")
    capture = commands.add_parser("save-list", help="save specification numbers from local filenames")
    capture.add_argument("--source", type=Path, default=DEFAULT_DIRECTORY)
    capture.add_argument("--list", type=Path, required=True)
    args = parser.parse_args()

    try:
        if args.command == "save-list":
            save_list(args.source.expanduser(), args.list.expanduser())
            return 0
        return download(load_specs(args.list.expanduser()), args.release, args.output.expanduser(), args.dry_run)
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    sys.exit(main())
