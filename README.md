# Vantage Core

**Unified Desktop Business Operating System**  
Construction • Real Estate • RV Resort

---

**One powerful, elegant platform to run your entire business.**

**Current Phase:** Foundation + Critical QuickBooks Import Module  
**Priority #1:** Complete, reliable migration of large, long-standing QuickBooks company files (Glen Canyon Construction LLC — in use since 1998)  
**GUI:** PyQt6 — Professional, native desktop experience  
**Database:** Enhanced with AIA/CSI cost codes, CIP tracking, depreciation, and time tracking foundation

---

## Vision

Vantage Core is a single, unified desktop application that lets you choose the industry mode when creating a new company:

- **Construction Management** (starting point)
- **Real Estate / Property Management** (Buildium-style with Utah & Arizona compliance)
- **RV Resort / Campground** (Campspot-style booking + Lightspeed POS integration)

All three modes share the same powerful core:
- Full double-entry accounting
- Complete QuickBooks import capability
- Integrated payroll & tax filing
- Bank reconciliation & payments
- Advanced project/job tracking
- Custom reporting engine

You will be able to run your construction company today, then later add real estate portfolios or RV resorts — all inside one elegant, high-performance desktop application.

**Single-user desktop first.** Multi-user support comes after the core is stable and powerful.

---

## Technology Stack

- **Python 3.13** + **PyQt6** (professional native UI)
- **SQLite** (single `.vantage` company file — portable and easy to backup)
- **SQLAlchemy** (clean data layer)
- **ReportLab** (high-quality PDF reports)
- Git for version control

```bash
pip install PyQt6 SQLAlchemy reportlab pandas openpyxl python-dateutil
```

---

## Key Capabilities (Construction Version)

### 1. Complete QuickBooks Migration
- Robust import engine for large, decades-old company files
- Supports IIF + CSV/Excel exports from QuickBooks
- Batch processing with detailed logging and resumability
- Smart matching using original QB internal IDs
- Post-import verification tools

### 2. Construction-Specific Features
- Full job costing with phases and cost codes
- **AIA/CSI cost code library** (seeded + customizable)
- **CIP (Construction in Progress)** tracking
- Depreciation & fixed asset management
- Work-in-Progress (WIP) schedules
- Progress billing and retainage
- Time tracking foundation (ready for mobile app sync)

### 3. Core Financial System
- Chart of Accounts with full tax line mapping
- Customers, Vendors, Employees
- Double-entry transaction engine
- Bank reconciliation
- Payroll engine + tax form generation
- Custom PDF reporting

### 4. Future Modules (Same Application)
- Real Estate / Property Management mode
- RV Resort mode with booking engine + POS integration
- Mobile time tracking companion app

---

## Project Structure

```
VantageCore/
├── core/
│   ├── database.py          # Schema + company file handling
│   ├── importer.py          # QuickBooks import engine
│   └── accounting.py
├── ui/                      # PyQt6 interface
├── reports/                 # PDF generation
├── construction/            # Job costing, WIP, etc.
├── payroll/
├── tax/
├── banking/
├── docs/
├── README.md
└── requirements.txt
```

---

## Current Status

- Database schema v0.2 complete (with AIA cost codes, CIP, depreciation, time_entries, import tracking)
- QuickBooks Import Engine started (IIF + CSV support + batch logging)
- Project rebranded as **Vantage Core**

**Next Priority:** Strengthen the QuickBooks importer so you can reliably migrate your large existing company file.

---

## Philosophy

Vantage Core is built to be **powerful yet elegant**.

It gives you complete control and visibility over your businesses without the bloat or subscription fatigue of traditional software. One desktop application. Your data. Your workflows. Your advantage.

---

*Built for operators who want clarity, control, and long-term ownership of their financial systems.*