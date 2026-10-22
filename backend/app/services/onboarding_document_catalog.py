"""Stable document keys, independent of editable application column titles."""
import json
from pathlib import Path

CATALOG_DIR = Path(__file__).resolve().parents[1] / "templates" / "onboarding"


def document_stages():
    return json.loads((CATALOG_DIR / "stages.json").read_text(encoding="utf-8"))


def document_variables():
    return json.loads((CATALOG_DIR / "variables.json").read_text(encoding="utf-8"))
