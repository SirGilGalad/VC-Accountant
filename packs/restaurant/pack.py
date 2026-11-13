"""Food, beverage, and tips on the shared chart."""

id = "restaurant"
name = "Restaurant"
description = "Food and beverage sales and cost."
company_home_sentence = "Record food and beverage sales and their cost on the shared ledger."

accounts = [
    ("1240", "Food & Beverage Inventory", "asset", None, None),
    ("2320", "Tips Payable", "liability", "payable", None),
    ("4800", "Food Sales", "income", None, None),
    ("4810", "Beverage Sales", "income", None, None),
    ("5800", "Food Cost", "cost_of_sales", None, None),
    ("5810", "Beverage Cost", "cost_of_sales", None, None),
    ("6810", "Kitchen Supplies", "expense", None, None),
]
