"""Industry pack ids. Extra accounts and screens arrive in later phases.

Phase 1 seeds only the base chart for every pack. A general company therefore
has no retainage, work in progress, or job-cost accounts.
"""

from __future__ import annotations

PACKS: list[tuple[str, str, str]] = [
    ("construction", "Construction", "Jobs, cost codes, and progress billing on the shared ledger."),
    ("property", "Real estate and property management", "Units, rent, and a document index for Utah and Arizona managers."),
    ("resort", "RV resort and campground", "Sites, cabins, and local reservation holds. Online booking is not connected."),
    ("general", "General business", "The shared chart only."),
    ("professional_services", "Professional services", "Fees, retainers, and engagements kept as jobs."),
    ("retail", "Retail", "Merchandise sales and purchases."),
    ("manufacturing", "Manufacturing", "Raw materials, work in process, and finished goods."),
    ("restaurant", "Restaurant", "Food and beverage sales and cost."),
    ("agriculture", "Agriculture", "Crop and livestock sales and farm costs."),
    ("nonprofit", "Nonprofit", "Contributions, grants, and net-asset classes."),
]

PACK_IDS: tuple[str, ...] = tuple(pack_id for pack_id, _name, _line in PACKS)


def pack_line(pack_id: str) -> str:
    for pid, _name, line in PACKS:
        if pid == pack_id:
            return line
    raise KeyError(pack_id)
