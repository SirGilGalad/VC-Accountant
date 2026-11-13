# Changelog

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
