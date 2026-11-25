import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

INSPECT = os.path.join(ROOT, ".claude", "skills", "3gpp-docx-structure", "scripts", "inspect_docx.py")
CHECK = os.path.join(ROOT, ".claude", "skills", "conversion-check", "scripts", "check_output.py")


@pytest.fixture(scope="session")
def inspect_mod():
    spec = importlib.util.spec_from_file_location("inspect_docx", INSPECT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Out:
    """Loaded conversion output."""

    def __init__(self, path):
        self.path = path
        self.manifest = json.load(open(os.path.join(path, "manifest.json"), encoding="utf-8"))
        self.clauses = self.manifest["clauses"]

    def entry(self, key):
        found = [c for c in self.clauses if c["clause"] == key]
        assert found, f"{key} not in manifest: {[c['clause'] for c in self.clauses]}"
        return found[0]

    def text(self, key):
        e = self.entry(key)
        assert e["file"], f"{key} has no file"
        with open(os.path.join(self.path, e["file"]), "rb") as f:
            return f.read().decode("utf-8")

    def body(self, key):
        return self.text(key).split("\n---\n", 1)[1]


@pytest.fixture
def convert(tmp_path):
    from spec2md.convert import SpecConverter

    def run(paths, **kw):
        if isinstance(paths, (str, os.PathLike)):
            paths = [paths]
        out_root = tmp_path / "out"
        conv = SpecConverter([str(p) for p in paths], str(out_root), quiet=True, **kw)
        conv.run()
        return Out(conv.out), conv
    return run
