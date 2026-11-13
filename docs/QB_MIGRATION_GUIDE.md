# Import from QuickBooks

**Goal:** Move a long-standing QuickBooks company, including Glen Canyon Construction LLC (in use since 1998), into VC Accountant with the history and balances the owner chooses to export. Nothing is called imported until the staged trial balance ties to the QuickBooks trial balance to the cent.


**Important Reality Check**
Directly reading `.QBW` or `.QBB` files is not practical. We use QuickBooks' own export tools (which are reliable) + our smart Import Wizard.

We will make the process as smooth and complete as possible. The importer is being built specifically with your large file in mind (batches, resumability, detailed logging, error recovery).

---

## Recommended Migration Strategy (Best Results)

### Phase 1: Prepare & Export from QuickBooks (Do this in your current QB)

1. **Open your Glen Canyon Construction company file** in QuickBooks Desktop (keep it installed for now).

2. **Export Lists (IIF format — best for master data)**
   - Go to **File → Utilities → Export → Lists to IIF Files**
   - Select and export these (one at a time or in groups):
     - Chart of Accounts
     - Customers
     - Vendors
     - Employees
     - Items (if you use them heavily)
     - Jobs (if available in your IIF export)
   - Save them with clear names like `GCC_ChartOfAccounts.iif`, `GCC_Customers.iif`, etc.

3. **Export Key Reports to Excel/CSV (for transactions & balances)**
   - Go to **Reports → Accountant & Taxes → Trial Balance**
     - Set date range to your fiscal year start or "All" if feasible
     - Export to Excel → `GCC_TrialBalance.xlsx`
   - Go to **Reports → Custom Reports → Transaction Detail by Account**
     - This is your main historical data source.
     - Recommended: Export in chunks if the file is huge
       - Example: One export per year or per 5-year block
       - Or filter by Account Type (e.g., all Job Cost accounts first)
     - Export to CSV/Excel with these columns at minimum:
       - Date, Num, Account, Debit, Credit, Memo, Job, Class, etc.
   - Also export:
     - **Job Profitability Summary** or **Job Transaction Detail**
     - **Customer Balance Detail**
     - **Vendor Balance Detail**
     - **Payroll reports** (if using QB Payroll)

4. **Optional but Recommended: Accountant's Copy**
   - Create an Accountant's Copy (File → Accountant's Copy → Save Accountant's Copy)
   - This can help with certain data integrity checks during import.

### Phase 2: Import into CDF (What we are building right now)

Once you have the exported files, you will use the **CDF Import Wizard** (PyQt6 interface we are developing):

1. Open VC Accountant → **Import from QuickBooks** (this command is hidden until the import phase).
2. Choose import type:
   - **Lists (IIF)** — Chart of Accounts, Customers, Vendors, Employees, Jobs
   - **Transactions (CSV/Excel)** — Historical journal entries, invoices, bills, checks, etc.
   - **Opening Balances** (from Trial Balance)
3. The wizard will:
   - Preview mappings (you can adjust)
   - Show potential duplicates or unmatched items
   - Run in batches with a progress bar
   - Log every action (viewable in Import Log screen)
   - Allow you to resume if interrupted
4. After import:
   - Run **Rebuild & Verify** (we will build this)
   - Compare Trial Balance in CDF vs QB
   - Spot-check a few old jobs for cost accuracy
   - Review the Import Log for any warnings

---

## Handling a Very Large Company File (Since 1998)

Your file likely contains tens of thousands (or more) of transactions. We are designing the importer to handle this, but here are smart strategies:

- **Full Import** — Possible but may take time. Do it over a weekend or in stages.
- **Recommended Hybrid Approach** (what most people do successfully):
  1. Import **all Lists** (Accounts, Customers, Vendors, Employees, Jobs) — fast
  2. Import **current/open jobs** with full history
  3. Import **last 5–7 years** of transactions in detail (most relevant for taxes, WIP, audits)
  4. Import **summary/beginning balances** for older closed jobs and accounts
  5. Archive or mark very old closed jobs as "Historical - Read Only"

We will build options in the Import Wizard for exactly this kind of selective + resumable import.

---

## Company file reading is not in this release

Import uses files exported from QuickBooks (lists, transaction detail, and a trial balance). Reading the company file directly is a later decision. It is not built, and this release does not include a connection into the running program.


---

## What We Will Preserve During Import

- Chart of Accounts + tax line mappings (as much as possible)
- Customer, Vendor, Employee lists with original QB internal IDs (for matching)
- Jobs with contract amounts, status, and cost history where available
- Historical transactions (invoices, bills, checks, journal entries, payroll)
- Job cost allocations (via Job + Cost Code on transaction lines)
- Account balances (via Trial Balance import + verification)
- Time tracking data (if you have it in QB)

What may need manual review after import:
- Very old custom item types or unusual account structures
- Some payroll tax history (we will rebuild current tax tables anyway)
- Complex multi-currency or inventory if you used advanced features

---

## Next Steps (Right Now)

1. Start exporting the **Lists to IIF** from your current QuickBooks (this is quick and safe).
2. Export a **Trial Balance** for the current fiscal year.
3. Let me know when you have a few sample IIF or CSV files ready — I can test the importer against them and refine the mapping logic immediately.
4. We will continue building the Import Wizard UI in PyQt6 so you have a guided, visual experience.

**This import capability is our top priority.** Once your data is safely in CDF, everything else (payroll, WIP reports, tax forms, banking, time tracking, and the future Real Estate / RV Resort modes) becomes much easier to build on a solid foundation.

You are not locked into QuickBooks anymore. We are building the exit ramp.

Let me know how you'd like to proceed with the next code drop (more importer logic, PyQt6 wizard skeleton, AIA cost code refinements, etc.).