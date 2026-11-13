"""Launch and company windows open, and closing a company does not quit."""

# Qt is optional in environments without its libraries. Imports stay below the skip.
# ruff: noqa: E402

import pytest

pytest.importorskip("PyQt6.QtWidgets", exc_type=ImportError)
pytest.importorskip("pytestqt", exc_type=ImportError)

from PyQt6.QtWidgets import QApplication, QPushButton

from core.packs import PACK_IDS
from core.services.companies import NewCompany, create_company_file
from desktop.forms import FORM_STATUS
from desktop.launch import LaunchWindow
from desktop.wizard import NewCompanyWizard


@pytest.fixture
def app(qtbot):
    instance = QApplication.instance() or QApplication([])
    instance.setQuitOnLastWindowClosed(False)
    return instance


def test_wizard_offers_exactly_the_pack_list(qtbot, app):
    wizard = NewCompanyWizard()
    qtbot.addWidget(wizard)
    assert wizard.pack_ids() == list(PACK_IDS)


def test_close_company_returns_to_launch(qtbot, app, tmp_path, monkeypatch):
    folder = tmp_path / "data"
    folder.mkdir()
    monkeypatch.setattr("core.services.preferences.data_dir", lambda: folder)
    monkeypatch.setattr("desktop.launch.data_dir", lambda: folder, raising=False)
    launch = LaunchWindow()
    qtbot.addWidget(launch)
    launch.show()
    engine, company_id, member_id = create_company_file(
        tmp_path / "red.vca",
        NewCompany(name="Red Mesa Builders LLC", legal_name="Red Mesa Builders LLC", pack_id="construction"),
    )
    launch._open_engine(tmp_path / "red.vca", engine, company_id, member_id)
    company = launch.company_window
    assert company.company_id == company_id
    assert company.name_label.wordWrap()
    assert company.form_status.text() == FORM_STATUS
    menus = [action.text().replace("&", "") for action in company.menuBar().actions()]
    assert menus == [
        "Company",
        "Customers",
        "Vendors",
        "Jobs",
        "Employees",
        "Banking",
        "Reports",
        "Lists",
    ]
    company.close()
    assert launch.isVisible()
    assert QApplication.instance() is not None
    labels = [button.text() for button in launch.findChildren(QPushButton)]
    assert "Import from QuickBooks" in labels
