# Changelog

## 2026-11-12 — Phase 5: online API behind a stub

- A development API exposes the same ledger services. It refuses to start unless `VCA_ENV` is `development`, and it binds to 127.0.0.1.
- The host subdomain selects the tenant. A company on another tenant is not returned. Postgres row policies enforce the same split.
- There is no sign-in. Uploading a desktop file returns 501 until that storage is specified.
- The web screens use the same eight sections and the company-home lanes.

Still refused: bank feeds, payments that leave the books, tax transmission, reading a company file directly, online booking, real sign-in, and sync. Those wait on a certified connection or on VCP Security Bot.

## 2026-11-12 — Phase 4: the other packs

- Property, resort, professional services, retail, manufacturing, restaurant, agriculture, and nonprofit companies seed their accounts on the shared chart.
- A pack number that already belongs to the base chart stays put. The pack account takes the next free number in that family. Payroll, wages, and rent expense are unchanged.
- A property company can charge rent and record a security deposit. The document index stores where a record is, not the file.
- A resort company can hold a site. Overlapping holds are refused. A guest deposit posts only when you record one. Nothing is booked online.

Still refused: bank feeds, payments that leave the books, tax transmission, reading a company file directly, online booking, and real sign-in. Those wait on a certified connection or on VCP Security Bot.

## 2026-11-12 — Phase 3: construction, layout, wizard

- A construction company gets the job-cost accounts and the starter cost codes. A general company does not.
- Job cost, billings, and over/under billing are computed. Time entered as hours:minutes is stored as minutes and is not posted until payroll exists.
- Company Home is six lanes beside the chart. The window opens maximized. Layout sizes are remembered per member, and a copy of the file keeps them.
- The wizard has a review page. Address and contact can prefill. Name and EIN do not, and the prefill file is outside the working folder.
- Reports export to CSV and PDF.

Still refused: bank feeds, payments that leave the books, tax transmission, reading a company file directly, online booking, and real sign-in. Those wait on a certified connection or on VCP Security Bot.

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
