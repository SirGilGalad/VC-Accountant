"""Inventory stages and product cost on the shared chart."""

id = "manufacturing"
name = "Manufacturing"
description = "Raw materials, work in process, and finished goods."
company_home_sentence = "Move cost through materials, labor, and overhead on the shared ledger."

accounts = [
    ("1210", "Raw Materials", "asset", None, None),
    ("1220", "Work in Process Inventory", "asset", None, None),
    ("1230", "Finished Goods", "asset", None, None),
    ("4700", "Product Sales", "income", None, None),
    ("5700", "Direct Materials", "cost_of_sales", None, None),
    ("5710", "Direct Labor", "cost_of_sales", None, None),
    ("5720", "Manufacturing Overhead", "cost_of_sales", None, None),
]
