# Questions for VCP Security Bot

Nothing in Phase 1 sends data off the machine. These decisions are still open. Do not invent answers in the ledger code.

1. Sign-in method for the online app, and how a session is stored.
2. Password policy, if passwords are used at all. No password field exists yet.
3. Tenant isolation review for `company.vantagecorepro.com`, including row-level security.
4. Where the database URL and keys live in hosting. No deploy config is in this repo.
5. Upload storage for company files and for the document index. The index is metadata only until this is decided.
6. Backups of the online database.
7. Whether a desktop `.vca` file may ever be uploaded, and how that upload is tied out.
8. Whether a full tax id or a full bank account number is ever stored, and how it would be encrypted. Today the books keep last-4 only. No routing numbers.

Until those answers exist, the desktop app stores the company on the local disk, keeps the optional EIN only in the company row, and does not sync.
