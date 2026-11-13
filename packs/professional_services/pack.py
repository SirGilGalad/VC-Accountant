"""Engagements stay on the shared job list. These are income and cost accounts only."""

id = "professional_services"
name = "Professional services"
description = "Fees, retainers, and engagements kept as jobs."
company_home_sentence = "Bill the engagement, record the cost, and read the reports."

accounts = [
    ("4500", "Professional Fees", "income", None, None),
    ("4510", "Reimbursable Expense Income", "income", None, None),
    ("5500", "Subcontracted Services", "cost_of_sales", None, None),
    ("6460", "Professional Liability Insurance", "expense", None, None),
    ("7350", "Licenses & Continuing Education", "expense", None, None),
]
