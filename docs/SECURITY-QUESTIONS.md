# Questions for VCP Security Bot

These are not decided. Nothing in this list is implemented.

1. Sign-in method. What proves a person is a member of a company?
2. Sessions. Where a session would live, how long it lasts, and how it ends.
3. Password policy, if passwords are used at all. Storage rules are not chosen. No password field exists yet.
4. Tenant isolation review. Confirm the row policies and the service-layer company check are enough, including the lookup function that reads a subdomain before the policy is set.
5. Secrets hosting. Where the database URL and any future keys live. They are not in this repo.
6. Upload storage for company files and for the document index. The index is metadata only until this is decided. The import routes stay closed.
7. Backups of an online company, and who can restore one.
8. Sync. Whether a desktop `.vca` file may ever be uploaded, and how that upload is tied out. It is not uploaded today.
9. Whether a full tax id or a full bank account number is ever stored, and how it would be encrypted. Today the books keep last-4 only. No routing numbers.

Until those answers exist, the desktop app stores the company on the local disk and does not sync.
