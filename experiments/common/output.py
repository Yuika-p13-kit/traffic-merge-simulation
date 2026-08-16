from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_metadata(path: Path, metadata: dict[str, Any]) -> Path:
    """Write reproducibility metadata in the shared JSON format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
