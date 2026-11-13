# Import

Move a company in from exported lists, a transaction-detail report, and a trial balance. Nothing is called imported until the staged trial balance matches that trial balance to the cent.

Reading a company file directly (`.QBW` or `.QBB`) is not in this release. That choice can be revisited later. This release uses the export files only.

Glen Canyon Construction LLC, in QuickBooks since 1998, is the first live company. Its files stay outside this repository.

## Export

In the desktop program:

1. **File → Utilities → Export → Lists to IIF Files.** Export the chart of accounts, customers (jobs come across as `Customer:Job`), vendors, employees, and other names. Items can be included. They are staged for reference and are not posted.
2. **Reports → Custom Reports → Transaction Detail by Account.** Export to CSV or Excel, one file per year or per block of years when the history is long. Keep Date, Num, Name, Account, Class, Debit, and Credit. A Trans # column is used when the report has one.
3. **Reports → Accountant & Taxes → Trial Balance** as of the cut-off date, to CSV or Excel. This is the number the import must tie to.

Put the files in a folder outside the repo, for example `Documents\VC Accountant\local-imports\`.

## Stage, tie, accept

1. Create the company, or open it.
2. From the launch screen, **Import from QuickBooks** runs the new-company wizard and then the import. On a company that is already open, use **Company → Import from QuickBooks…**.
3. Choose the files and the cut-off date. **Stage** parses them into staging tables and lists issues. The live books do not change.
4. The tie screen has three columns: the source trial balance, the staged trial balance, and the difference. Non-zero differences sort to the top. Totals sit on the last row. Click an account to see its staged lines.
5. Accept stays off until every difference is $0.00, every staged entry balances, and there are no error issues. The status is then `tied`.
6. **Accept** posts the staged entries in one database transaction. The status becomes `imported`.
7. **Reject** deletes that batch's staging rows. Journal rows are unchanged.
8. Staging the same files again updates the open batch. After Accept, the same files are refused and the earlier batch is named.

A file that cannot be read sets the batch to `failed` and records an issue. Fix the file and stage again.

For a long history, import the lists, then the recent years in detail, then use **Opening for years not in detail**. That adds one staged entry, dated the day before the cut-off, for the remaining difference. It does not run by itself. Tie again before Accept.

Account types that are not recognized are errors. They are not given a default type. A name that only partly matches an account is an error, not a guess.

## After Accept

Open Trial Balance and compare it with the source report. Open a few accounts in the General Ledger. Spot-check job cost against the job report you still have in the old program. Back up the company file.

If it does not tie, Reject, fix the export or the mapping, and stage again.
