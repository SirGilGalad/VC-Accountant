"""Resort accounts. Holds are local. No booking connection and no payment is taken here."""

id = "resort"
name = "RV resort and campground"
description = "Sites, cabins, and local reservation holds. Online booking is not connected."
company_home_sentence = "Hold a site locally, then record a guest deposit in the books when you actually receive it."

HOLD_BANNER = (
    "Local hold only. This is not an online booking, and no payment was taken. "
    "Online booking and point-of-sale systems are not connected."
)

accounts = [
    ("2430", "Guest Deposits", "liability", "payable", None),
    ("4400", "Site Rental", "income", None, None),
    ("4410", "Lodging", "income", None, None),
    ("4420", "Store Sales", "income", None, None),
    ("5400", "Store Cost of Goods", "cost_of_sales", None, None),
    ("6700", "Pool and Grounds", "expense", None, None),
]
