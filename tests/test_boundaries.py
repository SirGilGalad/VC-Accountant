"""Core stays free of UI and web frameworks."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {"PyQt6", "fastapi", "starlette", "uvicorn"}


def test_core_and_packs_do_not_import_ui():
    roots = [ROOT / "core", ROOT / "packs"]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module.split(".")[0]]
                else:
                    continue
                assert not (FORBIDDEN & set(names)), path
