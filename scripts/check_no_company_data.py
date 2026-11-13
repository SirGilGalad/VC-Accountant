"""Fail if company files or tax and bank identifiers are tracked."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN_SUFFIXES = {
    ".vca",
    ".vtg",
    ".vca.bak",
    ".qbw",
    ".qbb",
    ".qbm",
    ".qbx",
    ".tlg",
    ".nd",
    ".iif",
    ".csv",
    ".xlsx",
}
EIN = re.compile(r"\b\d{2}-\d{7}\b")
ROUTING = re.compile(r"routing\D{0,20}\d{9}|\d{9}\D{0,20}routing", re.IGNORECASE)
PLACEHOLDER = "XX-XXXXXXX"


def tracked_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def problems(root: Path) -> list[str]:
    found = []
    for rel in tracked_files(root):
        path = Path(rel)
        suffix = path.suffix.lower()
        if suffix in FORBIDDEN_SUFFIXES and "tests/fixtures/" not in rel.replace("\\", "/"):
            found.append(f"tracked company file: {rel}")
        full = root / rel
        if not full.is_file():
            continue
        if suffix in {".png", ".ico", ".docx"}:
            continue
        try:
            text = full.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in EIN.findall(text):
            if match == PLACEHOLDER:
                continue
            found.append(f"EIN-like number in {rel}")
            break
        if ROUTING.search(text) and "docs/SECURITY-QUESTIONS.md" not in rel.replace("\\", "/"):
            found.append(f"routing-number pattern in {rel}")
    return found


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    found = problems(root)
    if found:
        print("\n".join(found))
        return 1
    print("company data check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
