"""Typed failures from the ledger services."""


class LedgerError(Exception):
    """Base class for errors a person can be shown."""


class UnbalancedEntryError(LedgerError):
    def __init__(self, debits: int, credits: int):
        self.debits = debits
        self.credits = credits
        self.difference = debits - credits
        super().__init__(
            f"Unbalanced entry: debits {debits} credits {credits} difference {self.difference}"
        )


class TooFewLinesError(LedgerError):
    pass


class LineSideError(LedgerError):
    pass


class InactiveAccountError(LedgerError):
    pass


class WrongCompanyError(LedgerError):
    pass


class ClosedPeriodError(LedgerError):
    pass


class DuplicateAccountError(LedgerError):
    pass


class AccountNameError(LedgerError):
    pass


class ParentTypeError(LedgerError):
    pass


class RoleError(LedgerError):
    pass


class NotFoundError(LedgerError):
    pass
