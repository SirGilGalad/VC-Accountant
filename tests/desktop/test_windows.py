"""Launch and company windows open, and closing a company does not quit."""

# Qt is optional in environments without its libraries. Imports stay below the skip.
# ruff: noqa: E402

import pytest

pytest.importorskip("PyQt6.QtWidgets", exc_type=ImportError)
pytest.importorskip("pytestqt", exc_type=ImportError)

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QTreeWidget

from core.packs import PACK_IDS
from core.services.companies import NewCompany, create_company_file
from core.services.preferences import save_prefill
from desktop.forms import FORM_STATUS
from desktop.home import LANE_TITLES
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
    assert company.windowState() & Qt.WindowState.WindowMaximized
    titles = [label.text() for label in company.findChildren(QLabel) if label.objectName() == "lane-title"]
    assert titles == list(LANE_TITLES)
    assert company.splitter.orientation() == Qt.Orientation.Horizontal
    assert company.splitter.widget(1).findChild(QTreeWidget) is company.tree
    long_name = "N" * 70
    company.name_label.setText(long_name)
    assert company.name_label.wordWrap()
    assert company.name_label.alignment() & Qt.AlignmentFlag.AlignHCenter
    assert company.name_label.text() == long_name
    assert "…" not in company.name_label.text()
    side = [button.text() for button in company.findChildren(QPushButton)]
    for name in (
        "Company",
        "Customers",
        "Vendors",
        "Jobs",
        "Employees",
        "Banking",
        "Reports",
        "Lists",
    ):
        assert name in side


def test_wizard_prefills_address_but_not_name(qtbot, app, tmp_path, monkeypatch):
    monkeypatch.setattr("core.services.preferences.data_dir", lambda: tmp_path)
    monkeypatch.setattr("desktop.wizard.load_prefill", lambda: {
        "address1": "100 Sample Way",
        "city": "Kanab",
        "phone": "555-0100",
        "contact_name": "Pat Sample",
        "pack_id": "construction",
        "fiscal_year_start_month": 4,
        "accounting_method": "cash",
    })
    save_prefill({"address1": "100 Sample Way", "ein": "XX-XXXXXXX", "name": "Hidden"})
    wizard = NewCompanyWizard()
    qtbot.addWidget(wizard)
    assert wizard.name.text() == ""
    assert wizard.legal_name.text() == ""
    assert wizard.ein.text() == ""
    assert wizard.address1.text() == "100 Sample Way"
    assert wizard.page(4).title() == "Review"
