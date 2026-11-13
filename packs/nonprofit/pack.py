"""Net-asset classes and contribution accounts on the shared chart."""

id = "nonprofit"
name = "Nonprofit"
description = "Contributions, grants, and net-asset classes."
company_home_sentence = "Record contributions and the program, management, and fundraising costs."

accounts = [
    ("3300", "Net Assets Without Donor Restrictions", "equity", None, None),
    ("3310", "Net Assets With Donor Restrictions", "equity", None, None),
    ("4050", "Contributions", "income", None, None),
    ("4060", "Restricted Contributions", "income", None, None),
    ("4070", "Grants", "income", None, None),
    ("7800", "Program Services", "expense", None, None),
    ("7810", "Management & General", "expense", None, None),
    ("7820", "Fundraising", "expense", None, None),
]
