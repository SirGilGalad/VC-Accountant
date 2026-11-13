"""Shared fixtures. The sample company is fictional."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.services.companies import NewCompany, create_company_file

SAMPLE = NewCompany(
    name="Red Mesa Builders LLC",
    legal_name="Red Mesa Builders LLC",
    pack_id="construction",
    address1="100 Sample Way",
    city="Kanab",
    state="UT",
    postal_code="84741",
    ein=None,
    phone="555-0100",
    email="pat@example.com",
    contact_name="Pat Sample",
)


@pytest.fixture
def company(tmp_path: Path):
    engine, company_id, member_id = create_company_file(tmp_path / "red-mesa.vca", SAMPLE)
    return engine, company_id, member_id
