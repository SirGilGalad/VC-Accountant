"""Crop, livestock, and farm cost accounts on the shared chart."""

id = "agriculture"
name = "Agriculture"
description = "Crop and livestock sales and farm costs."
company_home_sentence = "Record crop and livestock sales and the farm costs that go with them."

accounts = [
    ("4900", "Crop Sales", "income", None, None),
    ("4910", "Livestock Sales", "income", None, None),
    ("4920", "Government Program Payments", "income", None, None),
    ("5900", "Seed & Fertilizer", "cost_of_sales", None, None),
    ("5910", "Feed", "cost_of_sales", None, None),
    ("5920", "Farm Labor", "cost_of_sales", None, None),
    ("6120", "Fuel & Machinery", "expense", None, None),
]
