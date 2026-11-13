"""Property accounts. Units and the document index are operational, not extra books."""

id = "property"
name = "Real estate and property management"
description = "Units, rent, and a document index for Utah and Arizona managers."
company_home_sentence = "Charge rent, hold deposits, and keep an index of the records you already have."

INDEX_NOTE = (
    "This index helps you find records. It is not legal advice. "
    "Confirm how long to keep each record with your attorney."
)
RETENTION_DEFAULT = "Confirm retention period with counsel."

accounts = [
    ("2420", "Security Deposits Held", "liability", "payable", None),
    ("4300", "Rental Income", "income", None, None),
    ("4310", "Late Fees", "income", None, None),
    ("4320", "Management Fees", "income", None, None),
    ("6600", "Property Maintenance", "expense", None, None),
    ("6610", "Property Utilities", "expense", None, None),
    ("6620", "HOA Fees", "expense", None, None),
    ("6630", "Property Taxes", "expense", None, None),
]
