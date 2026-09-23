"""Manifest reads and orchestration of the extract/load pipeline scripts."""

import json
import subprocess
import sys

from config.settings import MANIFEST_PATH, PIPELINE_DIR


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def run_pipeline_refresh(search_term: str, exact: bool) -> tuple[bool, str]:
    py = sys.executable
    steps = [
        [py, str(PIPELINE_DIR / "extract_to_json.py"), search_term] + (["--exact"] if exact else []),
        [py, str(PIPELINE_DIR / "load_sqlite.py")],
    ]
    log = []
    for step in steps:
        result = subprocess.run(step, cwd=PIPELINE_DIR, capture_output=True, text=True)
        log.append(result.stdout + result.stderr)
        if result.returncode != 0:
            return False, "\n".join(log)
    return True, "\n".join(log)
