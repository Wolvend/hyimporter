from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


def read_optional_csv(path: Path):
    if not path.exists():
        return None
    import csv

    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))
