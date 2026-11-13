"""Repo rules that are not ledger math."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_requirements_are_imported():
    import alembic  # noqa: F401
    import platformdirs  # noqa: F401
    import reportlab  # noqa: F401
    import sqlalchemy  # noqa: F401

    text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "SQLAlchemy" in text
    assert "alembic" in text
    assert "platformdirs" in text
    assert "PyQt6" in text
    assert "pandas" not in text.lower()


def test_company_data_check_flags_a_company_file(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "sample.QBW").write_bytes(b"not a real company file")
    subprocess.run(["git", "add", "sample.QBW"], cwd=repo, check=True, capture_output=True)
    result = subprocess.run(
        ["python", str(ROOT / "scripts" / "check_no_company_data.py"), str(repo)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "sample.QBW" in result.stdout


def test_form_status_says_nothing_was_sent():
    text = (ROOT / "desktop" / "forms.py").read_text(encoding="utf-8")
    assert "Nothing was sent" in text


def test_no_placeholder_dialogs():
    desktop = ROOT / "desktop"
    blob = "\n".join(path.read_text(encoding="utf-8") for path in desktop.rglob("*.py"))
    assert "will be" not in blob.lower()
    assert "to be defined" not in blob.lower()
    assert "Workflow Step" not in blob
