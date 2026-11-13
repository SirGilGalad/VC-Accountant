# Changelog

## 2026-11-12 — Phase 2: import

- Lists, transaction detail (CSV and XLSX), and a trial balance stage into their own tables. Nothing is posted until the staged trial balance matches the source trial balance to the cent and there are no error issues.
- Accept writes the batch in one transaction. Reject deletes the staging rows and leaves the books unchanged.
- The same files update the open batch instead of duplicating it. After Accept, staging them again does not post a second time.
- A file that cannot be read is `failed`, with an issue, and does not crash.
- Launch has Import, and an open company has the same command. Chart of Accounts, Trial Balance, General Ledger, and the customer, vendor, employee, and job lists are on the company window.
- Review screens show Customers, Vendors, Jobs, Employees, the trial balance, and the chart. Double-click an account for its register.

Still refused: bank feeds, payments that move money, tax transmission, reading a company file directly, online booking, and real sign-in. Those wait on a certified connection or on VCP Security Bot.

## 2026-11-12 — Phase 1: shared ledger

- One double-entry ledger in integer cents, with SQLAlchemy Core and an Alembic migration for SQLite and Postgres.
- Posting is checked in the service layer and again by database triggers. A one-sided entry cannot be posted.
- Balances, trial balance, and job figures are computed from posted lines. They are not stored.
- Every company starts from the base chart. Industry accounts are not seeded yet.
- Legacy `.vtg` files are backed up and opened as `.vca`. Unbalanced history stays in draft.
- Company files use `.vca`. The product name is VC Accountant.
- Save was removed. Back Up Company and Save a Copy As use the SQLite backup API.
- Closing a company returns to the launch screen. Exit is separate.
- Import from QuickBooks is hidden until Phase 2.

Still refused: bank feeds, payments that move money, tax transmission, reading a QuickBooks company file directly, online booking, and real sign-in. Those wait on a certified connection or on VCP Security Bot.
