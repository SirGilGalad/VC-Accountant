"""Every pack id creates a company on the base chart."""

from pathlib import Path

import pytest
from sqlalchemy import text

from core.packs import PACK_IDS
from core.queries import trial_balance_net
from core.services.companies import NewCompany, create_company_file


@pytest.mark.parametrize("pack_id", PACK_IDS)
def test_every_pack_creates_a_company(tmp_path: Path, pack_id: str):
    engine, company_id, _member = create_company_file(
        tmp_path / f"{pack_id}.vca",
        NewCompany(name="Red Mesa Builders LLC", legal_name="Red Mesa Builders LLC", pack_id=pack_id),
    )
    with engine.begin() as conn:
        stored = conn.execute(text("SELECT pack_id FROM companies WHERE id = :id"), {"id": company_id}).scalar()
        numbers = [row[0] for row in conn.execute(text("SELECT number FROM accounts"))]
        assert stored == pack_id
        assert len(numbers) == len(set(numbers))
        assert trial_balance_net(conn, company_id) == 0
        parents = conn.execute(
            text(
                """
                SELECT parent.number, child.number
                FROM accounts child
                JOIN accounts parent ON parent.id = child.parent_id
                """
            )
        ).all()
        for parent, child in parents:
            assert parent < child
