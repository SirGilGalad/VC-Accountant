"""New-company wizard. Address and contact can prefill. Name and EIN never do."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLineEdit,
    QWizard,
    QWizardPage,
)

from core.packs import PACKS
from core.services.preferences import load_prefill, save_prefill


class NewCompanyWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New company")
        self.company: dict = {}
        prefill = load_prefill()
        self.addPage(self._industry(prefill))
        self.addPage(self._identity())
        self.addPage(self._address(prefill))
        self.addPage(self._contact(prefill))

    def _industry(self, prefill: dict) -> QWizardPage:
        page = QWizardPage()
        page.setTitle("Industry")
        form = QFormLayout(page)
        self.pack = QComboBox()
        for pack_id, name, line in PACKS:
            self.pack.addItem(f"{name} — {line}", pack_id)
        index = self.pack.findData(prefill.get("pack_id") or "construction")
        if index >= 0:
            self.pack.setCurrentIndex(index)
        form.addRow("Pack", self.pack)
        return page

    def _identity(self) -> QWizardPage:
        page = QWizardPage()
        page.setTitle("Legal identity")
        form = QFormLayout(page)
        self.name = QLineEdit()
        self.legal_name = QLineEdit()
        self.ein = QLineEdit()
        self.entity = QComboBox()
        for value, label in (
            ("sole_prop", "Sole proprietorship"),
            ("llc", "LLC"),
            ("s_corp", "S corporation"),
            ("c_corp", "C corporation"),
            ("partnership", "Partnership"),
            ("nonprofit", "Nonprofit"),
            ("other", "Other"),
        ):
            self.entity.addItem(label, value)
        self.fy = QComboBox()
        for month in range(1, 13):
            self.fy.addItem(str(month), month)
        self.method = QComboBox()
        self.method.addItem("Accrual", "accrual")
        self.method.addItem("Cash", "cash")
        form.addRow("Company name", self.name)
        form.addRow("Legal name", self.legal_name)
        form.addRow("EIN (optional)", self.ein)
        form.addRow("Entity", self.entity)
        form.addRow("Fiscal year starts", self.fy)
        form.addRow("Method", self.method)
        return page

    def _address(self, prefill: dict) -> QWizardPage:
        page = QWizardPage()
        page.setTitle("Address")
        form = QFormLayout(page)
        self.address1 = QLineEdit(prefill.get("address1") or "")
        self.address2 = QLineEdit(prefill.get("address2") or "")
        self.city = QLineEdit(prefill.get("city") or "")
        self.state = QLineEdit(prefill.get("state") or "")
        self.postal = QLineEdit(prefill.get("postal_code") or "")
        self.country = QLineEdit(prefill.get("country") or "US")
        form.addRow("Address", self.address1)
        form.addRow("Address 2", self.address2)
        form.addRow("City", self.city)
        form.addRow("State", self.state)
        form.addRow("ZIP", self.postal)
        form.addRow("Country", self.country)
        return page

    def _contact(self, prefill: dict) -> QWizardPage:
        page = QWizardPage()
        page.setTitle("Contact")
        form = QFormLayout(page)
        self.phone = QLineEdit(prefill.get("phone") or "")
        self.email = QLineEdit(prefill.get("email") or "")
        self.contact_name = QLineEdit(prefill.get("contact_name") or "")
        self.contact_phone = QLineEdit(prefill.get("contact_phone") or "")
        self.contact_email = QLineEdit(prefill.get("contact_email") or "")
        form.addRow("Phone", self.phone)
        form.addRow("Email", self.email)
        form.addRow("Contact name", self.contact_name)
        form.addRow("Contact phone", self.contact_phone)
        form.addRow("Contact email", self.contact_email)
        return page

    def pack_ids(self) -> list[str]:
        return [self.pack.itemData(i) for i in range(self.pack.count())]

    def collected(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "legal_name": self.legal_name.text().strip() or self.name.text().strip(),
            "ein": self.ein.text().strip() or None,
            "pack_id": self.pack.currentData(),
            "entity_type": self.entity.currentData(),
            "fiscal_year_start_month": self.fy.currentData(),
            "accounting_method": self.method.currentData(),
            "address1": self.address1.text().strip(),
            "address2": self.address2.text().strip(),
            "city": self.city.text().strip(),
            "state": self.state.text().strip(),
            "postal_code": self.postal.text().strip(),
            "country": self.country.text().strip() or "US",
            "phone": self.phone.text().strip(),
            "email": self.email.text().strip(),
            "contact_name": self.contact_name.text().strip(),
            "contact_phone": self.contact_phone.text().strip(),
            "contact_email": self.contact_email.text().strip(),
        }

    def remember(self) -> None:
        data = self.collected()
        save_prefill(data)
