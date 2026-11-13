"""Values that stay inside this package."""

SOURCE_SYSTEM = "quickbooks"

QB_ACCOUNT_TYPES = {
    "BANK": ("asset", "bank"),
    "AR": ("asset", "receivable"),
    "OCASSET": ("asset", None),
    "FIXASSET": ("asset", "fixed_asset"),
    "OASSET": ("asset", None),
    "AP": ("liability", "payable"),
    "CCARD": ("liability", "credit_card"),
    "OCLIAB": ("liability", None),
    "LTLIAB": ("liability", None),
    "EQUITY": ("equity", None),
    "INC": ("income", None),
    "COGS": ("cost_of_sales", None),
    "EXP": ("expense", None),
    "EXINC": ("other_income", None),
    "EXEXP": ("other_expense", None),
}
