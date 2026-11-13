"""Construction accounts and cost codes. Money still posts through the shared ledger."""

id = "construction"
name = "Construction"
description = "Jobs, cost codes, and progress billing on the shared ledger."
company_home_sentence = "Bill the customer, run the job, record time, pay vendors, then read the job reports."

# number, name, type, subtype, parent number
accounts = [
    ("1130", "Retainage Receivable", "asset", "receivable", None),
    ("1400", "Work in Progress", "asset", None, None),
    ("1410", "Underbillings", "asset", None, "1400"),
    ("1460", "Prepaid Bond", "asset", None, None),
    ("2130", "Retainage Payable", "liability", "payable", None),
    ("2410", "Overbillings", "liability", None, None),
    ("4100", "Progress Billings", "income", None, None),
    ("4120", "Change-Order Revenue", "income", None, None),
    ("5000", "Job Costs", "cost_of_sales", None, None),
    ("5010", "Job Labor", "cost_of_sales", None, "5000"),
    ("5020", "Job Materials", "cost_of_sales", None, "5000"),
    ("5030", "Subcontractors", "cost_of_sales", None, "5000"),
    ("5040", "Equipment on Jobs", "cost_of_sales", None, "5000"),
    ("5050", "Other Job Costs", "cost_of_sales", None, "5000"),
    ("6450", "Bonding Expense", "expense", None, None),
]

# code, name, category, csi division
cost_codes = [
    ("01", "General Requirements", "other", "01"),
    ("03", "Concrete", "material", "03"),
    ("04", "Masonry", "material", "04"),
    ("05", "Metals", "material", "05"),
    ("06", "Wood & Plastics", "material", "06"),
    ("07", "Thermal & Moisture", "material", "07"),
    ("08", "Openings", "material", "08"),
    ("09", "Finishes", "material", "09"),
    ("22", "Plumbing", "subcontract", "22"),
    ("23", "HVAC", "subcontract", "23"),
    ("26", "Electrical", "subcontract", "26"),
    ("31", "Earthwork", "equipment", "31"),
    ("32", "Exterior Improvements", "material", "32"),
]
