"""Run spec2md from the plugin tree without installing it (pip fallback).

Preferred: uv run --project <plugin> spec2md <cmd> ...  (uv installs dependencies itself)
Fallback:  python spec2md.py <cmd> ...                 (after pip install -r requirements.txt)
"""
import os
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PLUGIN_ROOT, "src"))

try:
    import lxml  # noqa: F401
except ImportError:
    req = os.path.join(PLUGIN_ROOT, "requirements.txt")
    sys.stderr.write(f'lxml is required. Run with uv instead: uv run --project "{PLUGIN_ROOT}" spec2md ...\n'
                     f'  or install it: pip install -r "{req}"\n')
    raise SystemExit(3)

from spec2md.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
