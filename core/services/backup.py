"""SQLite online backup. Do not copy a live WAL file with a plain file copy."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def backup_file(source: Path | str, destination: Path | str) -> None:
    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(source)
    dst = sqlite3.connect(destination)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
