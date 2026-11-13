"""Merchandise accounts on the shared chart. No separate inventory ledger."""

id = "retail"
name = "Retail"
description = "Merchandise sales and purchases."
company_home_sentence = "Record the sale and the cost on the shared ledger."

accounts = [
    ("1200", "Merchandise Inventory", "asset", None, None),
    ("4600", "Merchandise Sales", "income", None, None),
    ("4610", "Sales Returns & Allowances", "income", None, None),
    ("5600", "Cost of Merchandise Sold", "cost_of_sales", None, None),
    ("5610", "Inventory Shrinkage", "cost_of_sales", None, None),
    ("6210", "Merchant Card Fees", "expense", None, None),
]
