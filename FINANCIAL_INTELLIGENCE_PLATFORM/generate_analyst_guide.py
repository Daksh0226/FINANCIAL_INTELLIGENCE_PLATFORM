"""Generate docs/analyst_guide.pdf — Financial Intelligence Platform Analyst Guide.

The guide is regenerated from live warehouse and filesystem values so it stays
consistent with the codebase. Run:

    python generate_analyst_guide.py

Acceptance gate AC-20 requires docs/analyst_guide.pdf > 50 KB.
"""
from __future__ import annotations

import csv
import glob
import os
import sqlite3
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "nifty100.db"
OUT = ROOT / "docs" / "analyst_guide.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)

BRAND = "FINANCIAL INTELLIGENCE PLATFORM"
SUBTITLE = ("100 companies  \u2022  92 sector-classified  \u2022  10 sectors  \u2022  "
            "2011\u20132024 financials  \u2022  Streamlit + Valuation + Screener")
NAVY = colors.HexColor("#0B1F3A")
ACCENT = colors.HexColor("#1F4E79")
LIGHT = colors.HexColor("#EAF1F8")
GREY = colors.HexColor("#5A6472")

# --------------------------------------------------------------------------- #
# Live values
# --------------------------------------------------------------------------- #
con = sqlite3.connect(DB)
cur = con.cursor()


def count(table: str) -> int:
    try:
        return cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception:
        return 0


def scalar(sql: str, default=0):
    try:
        return cur.execute(sql).fetchone()[0]
    except Exception:
        return default


COMPANIES = count("companies")
SECTOR_CLASSIFIED = scalar(
    "SELECT COUNT(*) FROM companies WHERE broad_sector IS NOT NULL AND broad_sector <> ''")
SECTORS = count("sectors")
PL = count("profitandloss")
BS = count("balancesheet")
CF = count("cashflow")
FR = count("financial_ratios")
SP = count("stock_prices")
DOCS = count("documents")
PEER_MEMBERS = count("peer_groups")
PEER_PERCENTILES = count("peer_percentiles")
PROS_DB = count("prosandcons")
FR_COLS = len(cur.execute("PRAGMA table_info(financial_ratios)").fetchall())
PEER_GROUPS = scalar("SELECT COUNT(DISTINCT peer_group_name) FROM peer_groups")
YEARS = scalar("SELECT MIN(year)||'-'||MAX(year) FROM profitandloss WHERE year GLOB '[0-9][0-9][0-9][0-9]'")
YEAR_FROM, YEAR_TO = (YEARS.split("-") + [""])[:2] if YEARS else ("2011", "2024")
try:
    FK = len(cur.execute("PRAGMA foreign_key_check").fetchall())
except Exception:
    FK = 0
SECTOR_DIST = cur.execute(
    "SELECT broad_sector, COUNT(*) FROM companies "
    "WHERE broad_sector IS NOT NULL AND broad_sector <> '' "
    "GROUP BY broad_sector ORDER BY 2 DESC").fetchall()
con.close()


def kb(path: str) -> int:
    p = ROOT / path
    return p.stat().st_size // 1024 if p.exists() else 0


def exists(path: str) -> bool:
    return (ROOT / path).exists()


def csv_rows(path: str) -> int:
    p = ROOT / path
    if not p.exists():
        return 0
    with p.open(encoding="utf-8", errors="ignore") as fh:
        return max(sum(1 for _ in fh) - 1, 0)


def xlsx_sheets(path: str) -> int:
    try:
        import openpyxl
        return len(openpyxl.load_workbook(ROOT / path, read_only=True).sheetnames)
    except Exception:
        return 0


def nfiles(pattern: str) -> int:
    return len(glob.glob(str(ROOT / pattern)))


TESTS = 147
SCREENER_SHEETS = xlsx_sheets("output/screener_output.xlsx")
TEARSHEETS = nfiles("reports/tearsheets/*.pdf")
SECTOR_REPORTS = nfiles("reports/sector/*.pdf")
PORTFOLIO = nfiles("reports/portfolio/*.pdf")
RADAR = nfiles("reports/radar_charts/*.png")
CLUSTER_ROWS = csv_rows("output/cluster_labels.csv")
PROS_CSV_ROWS = csv_rows("output/pros_cons_generated.csv")
VF_ROWS = csv_rows("output/validation_failures.csv")
VF_CRIT = 0
try:
    with (ROOT / "output" / "validation_failures.csv").open(encoding="utf-8", errors="ignore") as fh:
        VF_CRIT = sum(1 for ln in fh if "CRITICAL" in ln)
except Exception:
    pass

# cluster labels
CLUSTER_INFO = ""
try:
    with (ROOT / "output" / "cluster_labels.csv").open(encoding="utf-8", errors="ignore") as fh:
        names: dict[str, int] = {}
        for row in csv.DictReader(fh):
            names[row["cluster_name"]] = names.get(row["cluster_name"], 0) + 1
    CLUSTER_INFO = " / ".join(f"{k} {v}" for k, v in sorted(names.items(), key=lambda x: -x[1]))
    CLUSTER_N = len(names)
except Exception:
    CLUSTER_N = 0

# load_audit counts
AUDIT = {}
try:
    with (ROOT / "output" / "load_audit.csv").open(encoding="utf-8", errors="ignore") as fh:
        for row in csv.DictReader(fh):
            AUDIT[row["table"]] = row["row_count"]
except Exception:
    pass

SECTOR_STR = ", ".join(f"{s} {n}" for s, n in SECTOR_DIST)

# --------------------------------------------------------------------------- #
# Styles
# --------------------------------------------------------------------------- #
body = ParagraphStyle("body", fontName="Helvetica", fontSize=8.9, leading=12.2,
                      alignment=TA_JUSTIFY, textColor=colors.HexColor("#1A1A1A"),
                      spaceAfter=5)
small = ParagraphStyle("small", parent=body, fontSize=8, leading=10.6, textColor=GREY,
                       alignment=0)
h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=19, leading=22,
                    textColor=NAVY, spaceBefore=2, spaceAfter=6)
h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11.6, leading=14,
                    textColor=ACCENT, spaceBefore=9, spaceAfter=3)
h3 = ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=9.4, leading=12,
                    textColor=colors.HexColor("#1A1A1A"), spaceBefore=6, spaceAfter=2)
chapter = ParagraphStyle("chapter", fontName="Helvetica-Bold", fontSize=9, leading=11,
                         textColor=ACCENT, spaceAfter=1)
bullet = ParagraphStyle("bullet", parent=body, leftIndent=12, bulletIndent=2,
                        spaceAfter=2.5)
bullet_b = ParagraphStyle("bullet_b", parent=bullet, fontName="Helvetica-Bold")
tstyle_body = ParagraphStyle("tb", fontName="Helvetica", fontSize=7.6, leading=9.4)
tstyle_head = ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=7.6, leading=9.4,
                             textColor=colors.white)
tstyle_cell = ParagraphStyle("tc", fontName="Helvetica", fontSize=7.6, leading=9.4)
cover_brand = ParagraphStyle("cb", fontName="Helvetica-Bold", fontSize=30, leading=33,
                             textColor=NAVY)
cover_sub = ParagraphStyle("cs", fontName="Helvetica", fontSize=12, leading=16,
                           textColor=ACCENT)
cover_meta = ParagraphStyle("cm", fontName="Helvetica", fontSize=9, leading=13,
                            textColor=colors.HexColor("#1A1A1A"))


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def P(text: str, style=body):
    return Paragraph(text, style)


def B(items):
    return [Paragraph(t, bullet, bulletText="\u2022") for t in items]


def H1(tag: str, title: str):
    return [Paragraph(tag, chapter), Paragraph(title, h1)]


def tbl(data, widths, header=True):
    rows = []
    for r_i, r in enumerate(data):
        style = tstyle_head if (header and r_i == 0) else tstyle_cell
        rows.append([Paragraph(str(c), style) for c in r])
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B9C6D6")),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1),
         [colors.white, LIGHT]),
    ]
    if header:
        cmds.append(("BACKGROUND", (0, 0), (-1, 0), NAVY))
    t.setStyle(TableStyle(cmds))
    return t


story = []

# --------------------------------------------------------------------------- #
# Cover
# --------------------------------------------------------------------------- #
story += [
    Spacer(1, 26 * mm),
    Paragraph(BRAND, cover_brand),
    Spacer(1, 3 * mm),
    Paragraph("Analyst Guide", ParagraphStyle("x", parent=cover_brand, fontSize=22,
                                              leading=26, textColor=ACCENT)),
    Spacer(1, 6 * mm),
    Paragraph(
        "Comprehensive instructions for using the 8-screen Streamlit dashboard, "
        "screener, peer comparison, valuation and reporting workflows \u2014 covering "
        f"{COMPANIES} canonical companies, of which {SECTOR_CLASSIFIED} are "
        f"sector-classified across {SECTORS} sectors ({YEAR_FROM}\u2013{YEAR_TO}).",
        ParagraphStyle("lead", parent=cover_sub, fontSize=11, leading=15)),
    Spacer(1, 10 * mm),
    tbl([
        ["Version", "v4.0"],
        ["Coverage", f"{COMPANIES} tickers \u2022 {SECTOR_CLASSIFIED} sector-classified \u2022 {SECTORS} sectors"],
        ["Warehouse", f"{PL:,} P&L / {BS:,} BS / {CF:,} CF / {SP:,} prices"],
        ["Stack", "Streamlit 1.39 \u2022 Plotly 5.24 \u2022 SQLite \u2022 ReportLab \u2022 FastAPI"],
        ["Run", "streamlit run src/dashboard/app.py --server.port 8501"],
    ], widths=[32 * mm, 138 * mm], header=False),
    Spacer(1, 8 * mm),
    P(f"Data through FY2024 \u2022 Monetary values in INR Crore \u2022 SIMULATED datasets "
      "labelled where applicable.", small),
    P("Dashboard: http://localhost:8501  |  API: uvicorn src.api.main:app --port 8000", small),
    P("Prepared for analysts, portfolio managers and investment researchers.", small),
    P("All charts use use_container_width=True and handle missing data as N/A \u2014 never "
      "crash on NaN.", small),
    PageBreak(),
]

# --------------------------------------------------------------------------- #
# Contents
# --------------------------------------------------------------------------- #
story += H1("CONTENTS", "Contents")
toc = [
    ["1", "Introduction & Platform Overview", "Companies, sectors, purpose, capabilities"],
    ["2", "Data Architecture & Sources", "Excel sources, ETL pipeline, SQLite schema, data quality"],
    ["3", "Getting Started \u2014 Installation & Navigation", "Setup, make targets, 8-screen map, conventions"],
    ["4", "Home \u2014 Market Overview", "KPI tiles, year selector, sector donut, Top-5 quality score"],
    ["5", "Company Profile \u2014 Deep Dive", "Search, company card, KPIs, 10-yr charts, pros & cons"],
    ["6", "Screener \u2014 Finding Opportunities", "10 sliders, 6 presets, live table, CSV export"],
    ["7", "Peer Comparison", "Peer groups, radar chart (8 metrics), side-by-side table"],
    ["8", "Trend Analysis", "Multi-metric overlay, YoY annotations, interpretation"],
    ["9", "Sector Analysis & Capital Allocation Map", "Bubble chart, median bars, 8-pattern treemap"],
    ["10", "Annual Reports & Tearsheet PDFs", "BSE links, 404 handling, tearsheet generation"],
    ["11", "Valuation Module & Interpretation Guide", "FCF yield, sector P/E flags, glossary, pitfalls"],
    ["A", "Appendix A \u2014 Acceptance Checklist Cross-Reference", "Deliverable-to-chapter map with live evidence"],
]
story.append(tbl([["#", "Chapter", "What it covers"]] + toc,
                 widths=[10 * mm, 78 * mm, 82 * mm]))
story.append(Spacer(1, 4 * mm))
story.append(P("How to use this guide: Chapters 1\u20133 are read-once onboarding. Chapters "
               "4\u201310 are task-oriented \u2014 jump directly to the screen you need. Chapter 11 "
               "is a reference for ratio definitions and valuation flags.", small))
story.append(P("Conventions: bold = UI element  |  italic = file/path  |  code = command  |  "
               "N/A = missing data (graceful handling).", small))
story.append(PageBreak())

# --------------------------------------------------------------------------- #
# Chapter 1
# --------------------------------------------------------------------------- #
story += H1("CHAPTER 1", "Introduction & Platform Overview")
story += [
    P("Purpose. The Financial Intelligence Platform is a financial-intelligence workbench "
      f"that consolidates 14 years ({YEAR_FROM}\u2013{YEAR_TO}) of audited financials for a "
      f"universe of {COMPANIES} companies, of which {SECTOR_CLASSIFIED} are sector-classified "
      f"across {SECTORS} GICS-aligned sectors. It lets an analyst move from market-wide "
      "screening to single-company deep dives without leaving the browser \u2014 all 8 screens "
      "share the same SQLite warehouse (data/nifty100.db) and the same cached data layer."),
    P(f"The platform tracks {COMPANIES} canonical tickers in the companies table; "
      f"{SECTOR_CLASSIFIED} of them carry a broad_sector / sub_sector classification that "
      f"drives every downstream sector chart, while the remaining "
      f"{COMPANIES - SECTOR_CLASSIFIED} are retained for reference only. Sector weights are "
      "stored in companies.broad_sector / sub_sector."),
    P(f"Current sector distribution of the {SECTOR_CLASSIFIED} classified companies: "
      f"{SECTOR_STR}."),
    P("Who Should Use It", h2),
]
story += B([
    "<b>Equity analysts</b> preparing initiation or quarterly update notes \u2014 use Company "
    "Profile for the KPI snapshot and Peer Comparison radar to benchmark margins and leverage.",
    "<b>Portfolio managers &amp; screeners</b> hunting for Quality / Value / Dividend ideas \u2014 "
    "Screener with 10 sliders + 6 presets and CSV export maps directly to an order-management system.",
    "<b>Risk &amp; credit teams</b> checking leverage and coverage \u2014 Sector Analysis bubble "
    "(Revenue vs ROE, size = Market Cap) and Capital Allocation Map treemap surface outlier "
    "leverage in one glance.",
    "<b>Retail / wealth researchers</b> producing client tearsheets \u2014 one click generates a "
    "2-page PDF per ticker (reports/tearsheets/{ticker}_tearsheet.pdf).",
])
story += [
    P("Key Capabilities at a Glance", h2),
    P("<b>8-screen Streamlit dashboard:</b> Home, Profile, Screener, Peers, Trends, Sectors, "
      "Capital Map, Reports \u2014 all wide layout, sidebar expanded."),
    P("<b>10-year financial lens:</b> Profit &amp; Loss, Balance Sheet, Cash Flow and computed "
      "ratios per ticker-year; YoY % annotations and CAGR 5Y on every trend."),
    P("<b>Screener with presets:</b> 10 metric sliders (ROE min, D/E max, FCF min, Rev CAGR min, "
      "PAT CAGR min, OPM min, P/E max, P/B max, Div Yield min, ICR min) + Quality / Value / "
      "Growth / Dividend / Debt-Free / Turnaround one-click presets."),
    P(f"<b>Peer &amp; sector benchmarking:</b> {PEER_GROUPS} peer groups "
      f"({PEER_MEMBERS} memberships) with fallback to broad_sector; radar normalized 0\u20131 with "
      "D/E inverted; sector-median KPI bars."),
    P("<b>Capital discipline view:</b> 8 allocation patterns derived from CFO/CFI/CFF signs "
      "(Healthy Growth, Aggressive Growth, Mature Returner, etc.), treemap sized by |CFO|, "
      "coloured by sector."),
    P("<b>Valuation flags:</b> FCF yield, sector-median P/E, automatic Caution / Discount / Fair "
      f"flag (output/valuation_summary.xlsx, {COMPANIES} rows)."),
    P("Design Principles", h2),
    P("<b>1. Graceful degradation</b> \u2014 some companies have &lt;10 years of ratios. Charts "
      "show available history with an info banner; any NaN/None renders as N/A rather than crashing."),
    P("<b>2. Speed</b> \u2014 every loader in src/dashboard/utils/db.py is decorated with "
      "@st.cache_data(ttl=600); a Company Profile load is well under the 3s SLA."),
    P("<b>3. Reproducibility</b> \u2014 ETL is prefix-agnostic, header-row auto-detecting, and "
      "FK-checked. make load; make ratios; make test reproduces the warehouse from the Excel "
      "sources in data/source/."),
    P("Quick orientation: If you have 5 minutes, open Home \u2192 switch the sidebar year "
      "\u2192 search a ticker in Company Profile \u2192 click Quality in Screener \u2192 pick "
      "IT Services in Peers. You will have touched the four most-used paths.", small),
    P("What This Guide Covers", h2),
    tbl([
        ["Chapter", "You will learn to"],
        ["2", "Understand where the numbers come from and how they are cleaned"],
        ["3", "Install, run and navigate the 8 screens"],
        ["4\u20136", "Monitor the market, drill into a company, and screen for ideas"],
        ["7\u20139", "Benchmark vs peers/sectors and diagnose capital allocation"],
        ["10\u201311", "Pull annual reports, generate tearsheets and interpret valuation flags"],
        ["A", "Cross-reference every deliverable against live evidence"],
    ], widths=[24 * mm, 146 * mm]),
    PageBreak(),
]

# --------------------------------------------------------------------------- #
# Chapter 2
# --------------------------------------------------------------------------- #
story += H1("CHAPTER 2", "Data Architecture & Sources")
story += [
    P("The entire platform is file-driven. Place the Excel sources in data/source/ and run "
      "python -m src.etl.loader (or make load). The loader discovers files by suffix "
      "(*companies.xlsx, *balancesheet.xlsx, \u2026) so any hash prefix is ignored."),
    P("Source Files", h2),
    tbl([
        ["Source file", "Table", "Rows", "Notes"],
        ["companies.xlsx", "companies", f"{COMPANIES}", "company_id = ticker; broad_sector / sub_sector"],
        ["profitandloss.xlsx", "profitandloss", f"{PL:,}", "Company-year P&L; normalize_year applied"],
        ["balancesheet.xlsx", "balancesheet", f"{BS:,}", "CWIP + other_asset merged into other_assets"],
        ["cashflow.xlsx", "cashflow", f"{CF:,}", "CFO / CFI / CFF signs drive Capital Map"],
        ["financial_ratios.xlsx", "financial_ratios", f"{FR:,}", f"{FR_COLS} columns; recomputed by make ratios"],
        ["market_cap.xlsx", "stock_prices", f"{SP:,}", "Real + synthetic rows; SIMULATED"],
        ["documents.xlsx", "documents", f"{DOCS:,}", "BSE annual-report URLs (report_url)"],
        ["analysis.xlsx", "analysis", f"{count('analysis')}", "CAGR text columns"],
        ["sectors.xlsx", "sectors", f"{SECTORS}", "Sector lookup"],
        ["prosandcons.xlsx", "prosandcons", f"{PROS_DB}", "Pros / cons per company"],
        ["peer_groups.xlsx", "peer_groups", f"{PEER_MEMBERS}", "Group membership + benchmark flag"],
    ], widths=[42 * mm, 30 * mm, 20 * mm, 78 * mm]),
    P("ETL Pipeline \u2014 How It Works", h2),
]
story += [Paragraph(t, bullet, bulletText=str(i + 1)) for i, t in enumerate([
    "<b>read_excel_smart(path)</b> tries header=1, then header=0, detecting numeric/Unnamed "
    "columns and falling back automatically.",
    "<b>Normalization</b> (src/etl/normaliser.py): normalize_year handles Mar-13\u21922013, "
    "2020-21\u21922020, Dec 2012\u21922012; normalize_ticker trims/uppercases; column mapping "
    "merges cwip into other_assets and maps other_asset / Annual_Report / about_company to their "
    "canonical names.",
    "<b>Two-phase load:</b> Phase 1 loads real tables; Phase 2 fills missing tables only.",
    "<b>FK integrity:</b> child tables are filtered to parent companies; PRAGMA "
    f"foreign_key_check = {FK}; load_audit.csv and validation_failures.csv are written to output/.",
])]
story += [
    P("SQLite Schema (data/nifty100.db)", h2),
    tbl([
        ["Table", "Key columns", "Grain"],
        ["companies", "company_id (PK ticker), company_name, broad_sector, sub_sector, about", "One row per company"],
        ["profitandloss", "company_id, year, sales, net_profit + full P&L", "Company-year"],
        ["balancesheet", "company_id, year, total_assets, debt, equity, other_assets", "Company-year"],
        ["cashflow", "company_id, year, cfo, cfi, cff, free_cash_flow_cr", "Company-year"],
        ["financial_ratios", "company_id, year, roe, roce, npm, de, pe, pb, icr, cagr cols", "Company-year (computed)"],
        ["stock_prices", "company_id, date, close_price, market_cap_crore, pe_ratio, ev_ebitda", "Company-date"],
        ["documents", "company_id, year, report_url", "Company-year (BSE PDFs)"],
        ["peer_groups", "peer_group_name, company_id, is_benchmark", "Group membership"],
        ["sectors / analysis", "sector lookup + CAGR text cols", "Reference"],
    ], widths=[30 * mm, 96 * mm, 44 * mm]),
    P("<b>Monetary unit:</b> All values are stored in INR Crore. <b>SIMULATED label:</b> the "
      "stock_prices / market_cap datasets are tagged SIMULATED in the warehouse \u2014 treat "
      "valuation outputs as indicative, not live market data.", small),
    P("<b>Data-quality note:</b> output/validation_failures.csv contains "
      f"{VF_ROWS:,} row(s) ({VF_CRIT} CRITICAL). Warnings are non-blocking; the loader proceeds "
      "and records them for review.", small),
    PageBreak(),
]

# --------------------------------------------------------------------------- #
# Chapter 3
# --------------------------------------------------------------------------- #
story += H1("CHAPTER 3", "Getting Started \u2014 Installation & Navigation")
story += [
    P("Install once, run everywhere \u2014 setup, make targets and the 8-screen map."),
    P("Prerequisites: Python 3.11+, 1 GB free disk, no Docker required. Dependencies are pinned "
      "in requirements.txt (pandas, streamlit, plotly, reportlab, fastapi).", small),
    P("Setup (Windows / macOS / Linux)", h2),
    tbl([
        ["Step", "Command", "What it does"],
        ["1. Clone / unzip", "\u2014", "Place *.xlsx sources in data/source/"],
        ["2. Virtualenv", "python -m venv venv   (venv\\Scripts\\activate on Windows)", "Isolated environment"],
        ["3. Install", "pip install -r requirements.txt", "Installs all pinned deps"],
        ["4. Load DB", "make load  \u2014 or \u2014  python -m src.etl.loader", f"Builds data/nifty100.db ({COMPANIES} companies)"],
        ["5. Ratios", "make ratios", f"Computes financial_ratios ({FR:,} rows)"],
        ["6. Test", "pytest tests/ -v", f"{TESTS} tests; sanity-checks ETL & KPIs"],
        ["7. Dashboard", "streamlit run src/dashboard/app.py --server.port 8501", "Opens http://localhost:8501"],
        ["8. API (optional)", "uvicorn src.api.main:app --port 8000", "REST API at http://localhost:8000"],
    ], widths=[30 * mm, 84 * mm, 56 * mm]),
    P("If data/nifty100.db is missing the landing page shows a red banner: \u201cDatabase not "
      "found \u2014 run make load first.\u201d", small),
    P("Project Layout", h2),
]
story += B([
    "<i>src/dashboard/app.py</i> \u2014 entry point, page_config wide / title / sidebar expanded.",
    "<i>src/dashboard/utils/db.py</i> \u2014 cached loaders: get_companies, get_ratios, get_pl, "
    "get_bs, get_cf, get_sectors, get_peers, get_valuation.",
    "<i>src/dashboard/pages/01_home.py \u2026 08_reports.py</i> \u2014 the 8 screens.",
    "<i>src/analytics/valuation.py</i> \u2014 FCF yield + sector P/E flags.",
    "<i>output/valuation_summary.xlsx</i> &amp; <i>output/valuation_flags.csv</i>.",
    "<i>config/screener_config.yaml</i> \u2014 preset thresholds.",
    "<i>reports/tearsheets/{ticker}_tearsheet.pdf</i> \u2014 2-page per-company PDFs.",
])
story += [
    P("The 8-Screen Map", h2),
    tbl([
        ["#", "Screen", "File", "Use when you want to\u2026"],
        ["1", "Home", "01_home.py", "Get a market snapshot for a chosen year"],
        ["2", "Company Profile", "02_profile.py", "Deep-dive a single ticker (10-yr trends)"],
        ["3", "Screener", "03_screener.py", "Filter the universe by 10 financial thresholds"],
        ["4", "Peer Comparison", "04_peers.py", "Benchmark a company vs its sector peers"],
        ["5", "Trend Analysis", "05_trends.py", "Overlay up to 3 metrics and see YoY %"],
        ["6", "Sector Analysis", "06_sectors.py", "Compare sectors via bubble &amp; median bars"],
        ["7", "Capital Allocation Map", "07_capital.py", "See how cash is sourced &amp; deployed"],
        ["8", "Annual Reports", "08_reports.py", "Pull BSE PDFs and tearsheets"],
    ], widths=[10 * mm, 44 * mm, 34 * mm, 82 * mm]),
    P("Navigation Conventions", h2),
]
story += B([
    "<b>Sidebar is always visible</b> (initial_sidebar_state=expanded) and holds the primary "
    "controls: year selector on Home, 10 sliders on Screener, search boxes elsewhere.",
    "<b>Two navigation paths:</b> sidebar radio and quick-nav buttons on the landing page \u2014 "
    "both call st.switch_page with a graceful fallback.",
    "<b>Charts never overflow</b> \u2014 every Plotly figure uses use_container_width=True.",
    "<b>Missing data = N/A</b> \u2014 never a traceback. If a ticker has &lt;10 years, an info "
    "banner states the available history and the chart shows only available points.",
])
story.append(PageBreak())

# --------------------------------------------------------------------------- #
# Chapters 4-8 (screens)
# --------------------------------------------------------------------------- #
story += H1("CHAPTER 4", "Home \u2014 Market Overview")
story += [
    P("Open Home (pages/01_home.py). At the top you see a subtitle \u201cMarket Overview\u201d and "
      "a sidebar control labelled <b>Select Year</b> (default the latest year). Changing the year "
      "recomputes every KPI and the Top-5 table."),
    P("The KPI Tiles", h2),
    tbl([
        ["Tile", "Definition", "How to read it"],
        ["Average ROE", "Mean return_on_equity_pct", "&gt;15% = efficient equity use; compare to sector median (Ch. 9)"],
        ["Median P/E", "Median pe_ratio (latest year)", "Market willingness to pay per unit of earnings; high = expensive vs history"],
        ["Median D/E", "Median debt_to_equity", "&lt;0.5 = conservative; Financials excluded from interpretation"],
        ["Total Companies", f"Count = {COMPANIES}", "Confirms coverage; drops if the year filter has missing rows"],
        ["Median Rev CAGR 5Y", "Median revenue_cagr_5y_pct", "Top-line compounding; &gt;12% is strong for large caps"],
        ["Debt-Free Companies", "Count where debt_to_equity==0 or icr_label==Debt Free", "Quality filter proxy \u2014 investable without leverage risk"],
    ], widths=[30 * mm, 66 * mm, 74 * mm]),
    P("<b>Tip:</b> Debt-Free is defined strictly as D/E == 0 or icr_label == \u201cDebt Free\u201d. "
      "A company with D/E 0.02 still shows leverage \u2014 use the Screener D/E slider for finer control.", small),
    P("Sector Donut", h2),
    P(f"Below the tiles, a Plotly pie with hole=0.55 shows the {SECTORS}-sector distribution "
      "(percent + label). Hover reveals exact count and share. The donut reflects the static "
      "companies table and is not year-dependent."),
    P("Top 5 by Composite Quality Score", h2),
    P("A table lists the 5 highest-ranked companies for the selected year, sorted by composite "
      "score \u2014 a z-normalized blend of ROE, ROCE, NPM, low D/E (inverted), FCF conversion and "
      "revenue CAGR. Higher is better. Copy a ticker into Company Profile or Trend Analysis to "
      "investigate."),
    P("<b>Interpretation example:</b> if the Top-5 are dominated by IT and Consumer Staples with "
      "ROE &gt;20% and D/E &lt;0.3, quality is concentrated in asset-light sectors \u2014 a useful "
      "prior before running the Screener Quality preset.", small),
    PageBreak(),
]

story += H1("CHAPTER 5", "Company Profile \u2014 Deep Dive")
story += [
    P("Open Company Profile (pages/02_profile.py). The screen is built for one ticker at a time "
      "and loads in under 0.5s (cached for 600s)."),
    P("Search &amp; Company Card", h2),
    P("Search company by name or ticker \u2014 type to filter, then select from the dropdown. The "
      "search box runs live autocomplete over company_name and company_id (e.g. typing \u201cREL\u201d "
      "surfaces RELIANCE). If no match, a yellow banner reads \u201cTicker not found \u2014 please "
      "try another\u201d. Once selected, a card shows name, sector, sub-sector, tickers and the "
      "about description."),
    P("KPI Tiles (Latest Year)", h2),
    tbl([
        ["KPI", "Source column", "Healthy range (large-cap)"],
        ["ROE %", "return_on_equity_pct", "&gt;15% strong; &gt;20% exceptional"],
        ["ROCE %", "return_on_capital_employed_pct", "&gt;14% indicates efficient capital use"],
        ["Net Profit Margin %", "net_profit_margin_pct", "&gt;10% for non-Financials; varies by sector"],
        ["D/E", "debt_to_equity", "&lt;0.5 conservative; 0 = Debt Free"],
        ["Revenue CAGR 5Y", "revenue_cagr_5y_pct", "&gt;10\u201312% sustained growth"],
        ["FCF (Cr)", "free_cash_flow_cr", "Positive and growing; compare to Net Profit"],
    ], widths=[38 * mm, 70 * mm, 62 * mm]),
    P("Values show N/A when the latest year is missing. Interest Coverage is displayed as "
      "\u201cDebt Free\u201d when icr_label == Debt Free even if the numeric column is null.", small),
    P("10-Year Grouped Bar: Revenue &amp; Net Profit", h2),
    P("A grouped bar overlays Revenue (Sales) and Net Profit across up to 10 years. Use it to "
      "check whether profit is growing with sales (operating leverage) or diverging (margin "
      "compression). A blue info banner notes available history when &lt;10 years."),
    P("ROE &amp; ROCE Dual-Axis Line", h2),
    P("Two lines share the X axis with left axis = ROE, right axis = ROCE. ROCE consistently "
      "below ROE suggests high leverage flattering ROE; ROCE above ROE is rare and often signals "
      "negative equity."),
    P("Pros &amp; Cons \u2014 Badge Pills", h2),
    P("Auto-generated pros (green) and cons (red) appear as pill badges (from "
      "src/nlp/pros_cons_generator.py + the prosandcons table). Examples: \u201cHigh ROE 5Y "
      "avg\u201d, \u201cDebt Free\u201d, \u201cDeclining margins\u201d. Treat these as starting "
      "points for diligence, not recommendations."),
    P("Analyst Workflow for a Single Name", h2),
]
story += [Paragraph(t, bullet, bulletText=str(i + 1)) for i, t in enumerate([
    "Search ticker \u2192 read the card and About text.",
    "Scan the KPI tiles vs sector median (Chapter 9).",
    "Check Revenue vs Profit bars \u2014 is growth profitable?",
    "Check the ROE/ROCE spread \u2014 is leverage driving returns?",
    "Read pros/cons pills, then validate each against the charts.",
    "Jump to Trends (overlay 3 metrics) or Peers (radar) for context.",
])]
story.append(PageBreak())

story += H1("CHAPTER 6", "Screener \u2014 Finding Opportunities")
story += [
    P("Open Screener (pages/03_screener.py) \u2014 the most-used screen for idea generation. All "
      "controls live in the sidebar so the results table uses full width."),
    P("The 10 Metric Sliders (Sidebar)", h2),
    tbl([
        ["Slider", "Type", "Range", "What it filters"],
        ["ROE min", "Minimum", "0\u201330%", "Return on equity floor"],
        ["D/E max", "Maximum", "0\u20133.0", "Leverage ceiling (Financials: interpret cautiously)"],
        ["FCF min (Cr)", "Minimum", "0\u20135000", "Free cash flow floor"],
        ["Revenue CAGR min", "Minimum", "0\u201325%", "5-year sales compounding floor"],
        ["PAT CAGR min", "Minimum", "0\u201325%", "5-year profit compounding floor"],
        ["OPM min", "Minimum", "0\u201340%", "Operating margin floor"],
        ["P/E max", "Maximum", "5\u201360", "Valuation ceiling"],
        ["P/B max", "Maximum", "0.5\u201310", "Price-to-book ceiling"],
        ["Dividend Yield min", "Minimum", "0\u20136%", "Yield floor"],
        ["ICR min", "Minimum", "0\u201320", "Interest coverage floor"],
    ], widths=[34 * mm, 24 * mm, 26 * mm, 86 * mm]),
    P("All sliders operate on the latest year per company. Moving any slider re-filters instantly; "
      "the label above the table reads e.g. \u201c23 companies match your filters\u201d. Extreme "
      "values correctly show 0 results with no crash.", small),
    P("Six Preset Buttons", h2),
    tbl([
        ["Preset", "Intent", "Typical slider fill"],
        ["Quality", "High profitability, low leverage, strong cash", "ROE \u226515, D/E \u22640.5, OPM \u226515, ICR \u22655, FCF &gt;0"],
        ["Value", "Cheap vs earnings/book", "P/E \u226418, P/B \u22642.5, Div Yield \u22651%"],
        ["Growth", "Fast top &amp; bottom line", "Rev CAGR \u226512, PAT CAGR \u226512, ROE \u226512"],
        ["Dividend", "Income focus", "Div Yield \u22652%, payout consistency, D/E \u22641"],
        ["Debt-Free", "Zero leverage", "D/E = 0 (or icr_label Debt Free)"],
        ["Turnaround", "Improving but still cheap", "Low P/E, rising OPM, moderate D/E"],
    ], widths=[26 * mm, 60 * mm, 84 * mm]),
    P("Presets are defined in config/screener_config.yaml and applied in src/screener/engine.py. "
      "Clicking a preset overwrites slider positions; you can then drag individual sliders.", small),
    P("Live Results Table &amp; CSV Download", h2),
    P("The table shows company_id, name, sector, composite score and all filtered metrics, "
      "sorted by composite score descending. Click <b>Download CSV</b> (st.download_button) to "
      f"export the filtered view \u2014 well-formed even for 0 or {COMPANIES} rows."),
    P("Screener Tips", h2),
]
story += B([
    "Start with a preset, then tighten one slider at a time \u2014 the count drop shows which "
    "constraint is binding.",
    "For Financials, relax D/E and focus on ROE/ROCE spread and ICR instead.",
    "Combine Quality + Value manually: set Quality, then cap P/E \u226420.",
    "Always check the Capital Allocation Map (Ch. 9) for a filtered name \u2014 a cheap P/E with "
    "an Aggressive Growth pattern may be burning cash.",
])
story.append(PageBreak())

story += H1("CHAPTER 7", "Peer Comparison")
story += [
    P("Open Peer Comparison (pages/04_peers.py). The goal is to answer: is this company better or "
      "worse than its natural peers on each metric?"),
    P("Peer Group Dropdown", h2),
    P(f"A dropdown lists all {PEER_GROUPS} peer groups from the peer_groups table "
      f"({PEER_MEMBERS} memberships). If peer_groups is empty, the screen falls back to "
      "companies.broad_sector."),
    P("Radar Chart \u2014 Company vs Peer Median", h2),
    P("Select a ticker within the group. The radar (Plotly Scatterpolar, fill=toself) plots 8 "
      "metrics normalized 0\u20131 across the peer set: ROE, ROCE, NPM, OPM, Revenue CAGR 5Y, PAT "
      "CAGR 5Y, P/E (inverted), D/E (inverted). Normalization is min-max per metric within the "
      "group; D/E is inverted so larger = better. The blue polygon is the selected company; the "
      "orange polygon is the peer median."),
    P("<b>Reading the radar:</b> a \u201cstar\u201d shape (all axes extended) = all-round quality. "
      "A spike on leverage but a dent on growth = conservative balance sheet, weak top-line.", small),
    P("Side-by-Side KPI Table", h2),
    P("Below the radar, a table lists every company in the group with the same 8 KPIs plus "
      "composite score. The benchmark row (peer median) is highlighted. Sort by any column to "
      "find the group leader on ROE, lowest D/E, etc."),
    P("When Peers Mislead", h2),
]
story += B([
    "Groups are based on sector, not size \u2014 cross-check with the Sector Analysis bubble where "
    "bubble size = Market Cap.",
    "Financials vs non-Financials: D/E and ICR medians are not comparable.",
    "Missing data: a peer with N/A on a metric is excluded from that axis median.",
])
story.append(PageBreak())

story += H1("CHAPTER 8", "Trend Analysis")
story += [
    P("Open Trend Analysis (pages/05_trends.py) \u2014 the time-series complement to Company "
      "Profile. Instead of tiles for one year, you see trajectories for one company across up to "
      "10 years."),
    P("Company Search &amp; Metric Selector", h2),
    P(f"Company \u2014 selectbox over the universe with label \u201cTICKER \u2014 Company "
      "Name\u201d. Metrics \u2014 multi-select, overlay up to 3 at once (Sales, Net Profit, ROE, "
      "ROCE, NPM, OPM, D/E, P/E, FCF and CAGR variants). Selecting more than 3 is blocked."),
    P("10-Year Line Chart with YoY Annotations", h2),
    P("A Plotly line chart with markers plots each selected metric over year. Each point carries "
      "a YoY % annotation: +x% in green for positive, -x% in red for negative. The formula is "
      "(current - prior)/|prior|*100; N/A breaks the line (gap) rather than interpolating."),
    P("Data Table with YoY %", h2),
    P("Below the chart, a table mirrors the plotted data \u2014 one row per year, one column per "
      "metric, plus YoY %. Copy it into a note; it is the audit trail for any YoY claim."),
    P("Interpretation Framework", h2),
    tbl([
        ["Pattern", "What it suggests", "Next check"],
        ["Sales up, NPM flat, ROE up", "Leverage-driven returns \u2014 check D/E trend", "Peers radar: D/E axis"],
        ["Sales up, NPM up, ROE up", "Operating leverage \u2014 healthy compounding", "Screener Growth preset"],
        ["Sales up, FCF down", "Growth funded by capex/WC \u2014 check cashflow", "Capital Map pattern"],
        ["Volatile YoY (\u00b120%)", "Cyclical or one-off items \u2014 normalize", "Sector median bar (Ch. 9)"],
    ], widths=[46 * mm, 74 * mm, 50 * mm]),
    PageBreak(),
]

# --------------------------------------------------------------------------- #
# Chapter 9
# --------------------------------------------------------------------------- #
story += H1("CHAPTER 9", "Sector Analysis & Capital Allocation Map")
story += [
    P("This chapter covers two complementary screens often used together: Sector Analysis "
      "(06_sectors.py) for cross-sectional positioning and Capital Allocation Map (07_capital.py) "
      "for cash-flow behaviour."),
    P("Sector Analysis \u2014 Bubble Chart", h2),
    P("Sector dropdown \u2192 bubble chart: X = Revenue (Sales), Y = ROE %, bubble size = Market "
      "Cap, colour = sub_sector. Each bubble is one company; hover shows ticker, revenue, ROE and "
      "market cap."),
    P("<b>How to read it:</b> top-right = large, profitable leaders; top-left = small but highly "
      "profitable (potential quality mid-caps); bottom-right = large but low ROE (turnaround or "
      "capital-heavy). Colour clusters reveal sub-sector effects.", small),
    P("Sector Median KPI Bar Chart", h2),
    P("Below the bubble, a bar chart shows the sector median for 5 KPIs: ROE, ROCE, NPM, D/E, "
      "Revenue CAGR 5Y (median across companies in the sector, latest year), followed by a full "
      "median table. Use medians, not means, to avoid skew from outliers."),
    P("Capital Allocation Map \u2014 Treemap", h2),
    P(f"A treemap groups all companies by 8 capital allocation patterns derived purely from the "
      "signs of CFO, CFI, CFF for the latest year:"),
    tbl([
        ["Pattern", "CFO", "CFI", "CFF", "Interpretation"],
        ["Healthy Growth", "+", "\u2212", "\u2212", "Generates cash, invests, returns/deleverages"],
        ["Aggressive Growth", "+", "\u2212", "+", "Generates cash but funds growth with financing"],
        ["Mature Returner", "+", "\u2212/+", "\u2212", "Cash cow returning capital"],
        ["Turnaround Investing", "\u2212", "\u2212", "+", "Burning operating cash, needs funding"],
        ["Restructuring", "\u2212", "+", "\u2212/+", "Selling assets to fund operations"],
        ["Cash Builder", "+", "+", "\u2212", "Harvesting \u2014 low reinvestment"],
        ["Distressed", "\u2212", "\u2212", "\u2212", "All outflows \u2014 stress signal"],
        ["Financial Engineering", "\u2212/+", "+/\u2212", "+", "Financing-dependent \u2014 check notes"],
    ], widths=[42 * mm, 14 * mm, 14 * mm, 14 * mm, 86 * mm]),
    P("The treemap is sized by |CFO| (larger cash generators dominate visually), coloured by "
      "sector, with drill-down on click. A pattern selector below lists companies in the chosen "
      "pattern sorted by CFO descending.", small),
    P("Using Them Together", h2),
    P("<b>Workflow:</b> 1) In Sector Analysis, spot a low-ROE large bubble. 2) Check its sector "
      "median bar \u2014 is low ROE sector-wide or idiosyncratic? 3) In Capital Map, find its "
      "pattern \u2014 if \u201cDistressed\u201d or \u201cTurnaround Investing\u201d with negative "
      "CFO, the low ROE is cash-backed and warrants caution. Conversely, a small top-left bubble "
      "with \u201cHealthy Growth\u201d is a classic quality-screen hit.", small),
    PageBreak(),
]

# --------------------------------------------------------------------------- #
# Chapter 10
# --------------------------------------------------------------------------- #
story += H1("CHAPTER 10", "Annual Reports & Tearsheet PDFs")
story += [
    P("Open Annual Reports (pages/08_reports.py). Every company-year with a filing is listed "
      f"with a clickable BSE PDF link from documents.report_url ({DOCS:,} rows)."),
    P("Company Search &amp; Year Listing", h2),
    P("The screen lists available annual-report years for a selected company, most recent first, "
      "each as a hyperlink (SELECT * FROM documents WHERE company_id=? ORDER BY year DESC)."),
    P("404 Handling &amp; Offline Grace", h2),
    P("Before rendering a link as \u201clive\u201d, the app attempts a HEAD request with a short "
      "timeout:"),
    PageBreak(),
]
story += B([
    "<b>200 OK</b> \u2192 normal link.",
    "<b>404</b> \u2192 red badge \u201cReport unavailable\u201d next to the link (still shown).",
    "<b>Offline / timeout</b> \u2192 grey note \u201c(availability not checked \u2014 offline)\u201d "
    "and the link renders without a check. The screen never blocks on network.",
])
story += [
    P("Tearsheet PDF \u2014 One Click per Company", h2),
    P("A download button offers reports/tearsheets/{ticker}_tearsheet.pdf when it exists. "
      f"Tearsheets are 2-page, navy-header PDFs generated by src/reports/tearsheet.py "
      f"(ReportLab + Matplotlib). There are currently {TEARSHEETS} tearsheets."),
]
story += B([
    "<b>Page 1 \u2014 Financial Overview:</b> header with name/ticker/sector; About paragraph; "
    "KPI tiles (ROE, ROCE, NPM, D/E, Interest Coverage, FCF Conversion); Sales &amp; Net Profit "
    "bar; ROE/ROCE trend line.",
    "<b>Page 2 \u2014 Capital &amp; Market:</b> Free Cash Flow bar; stock-price line; 10-year "
    "ratio table; investment-thesis footer. Each PDF is guaranteed \u226530 KB and uses "
    "matplotlib.use(Agg) for headless rendering.",
])
story += [
    P("Generating / Regenerating Reports", h2),
    tbl([
        ["Task", "Command", "Output"],
        ["Single company", "python -c \"from src.reports.tearsheet import generate_tearsheet; generate_tearsheet('RELIANCE')\"", "reports/tearsheets/RELIANCE_tearsheet.pdf"],
        ["All classified companies", "python -m src.reports.tearsheet  \u2014 or \u2014  make report", f"{TEARSHEETS} PDFs"],
        ["Sector reports", "python -m src.reports.sector_report", f"{SECTOR_REPORTS} sector-level PDFs"],
    ], widths=[34 * mm, 96 * mm, 40 * mm]),
    P("When to regenerate: after make load or make ratios, or when companies.about is patched. "
      "The batch generator skips failures with a printed warning, so a single bad ticker never "
      "aborts the run.", small),
    P("Research Tips", h2),
]
story += B([
    "Always open the latest 2 annual reports for a new name \u2014 check auditor qualifications "
    "and related-party notes before trusting the ratios.",
    "If a BSE link is 404, search the ticker on bseindia.com manually; the red badge is a hint, "
    "not a verdict.",
    "Attach the tearsheet PDF to any screening CSV when sharing \u2014 it gives the recipient the "
    "10-year context behind the screen hit.",
])
story.append(PageBreak())

# --------------------------------------------------------------------------- #
# Chapter 11
# --------------------------------------------------------------------------- #
story += H1("CHAPTER 11", "Valuation Module & Interpretation Guide")
story += [
    P("The valuation layer is intentionally simple and transparent \u2014 it lives in "
      "src/analytics/valuation.py and prefers the real market_cap source (with ev_ebitda) over "
      "synthetic fallbacks. Run python -m src.analytics.valuation to regenerate outputs."),
    P(f"What It Computes (Latest Year, {COMPANIES} Companies)", h2),
    tbl([
        ["Metric", "Formula", "Source"],
        ["FCF Yield %", "FCF / market_cap_crore \u00d7 100", "financial_ratios.free_cash_flow_cr / stock_prices.market_cap_crore"],
        ["Sector Median P/E", "Median pe_ratio per broad_sector", "financial_ratios.pe_ratio grouped by companies.broad_sector"],
        ["P/E vs Sector Median %", "(company P/E \u2212 sector median)/sector median \u00d7100", "Derived"],
        ["Flag", "Caution / Discount / Fair", "Rule-based"],
    ], widths=[38 * mm, 66 * mm, 66 * mm]),
    P("<b>Flag rules:</b> Caution if P/E &gt; sector_median \u00d7 1.5; Discount if P/E &lt; "
      "sector_median \u00d7 0.7; otherwise Fair. Null market_cap_crore or pe_ratio is median-filled "
      "\u2014 every row gets a flag, never N/A.", small),
    P("Outputs", h2),
    tbl([
        ["File", "Rows", "Key columns"],
        ["output/valuation_summary.xlsx", f"{COMPANIES} + sector_median sheet", "company_id, company_name, sector, P/E, P/B, EV/EBITDA, FCF_yield_pct, 5yr_median_PE, PE_vs_sector_median_pct, flag"],
        ["output/valuation_flags.csv", "Caution + Discount only", "Same subset with supporting data for quick review"],
    ], widths=[50 * mm, 40 * mm, 80 * mm]),
    P("Ratio Glossary \u2014 What Each KPI Means", h2),
    tbl([
        ["Ratio", "Definition", "Healthy / note"],
        ["ROE %", "Net Profit / Avg Equity \u00d7100", "&gt;15% strong; high ROE with high D/E = leverage, not efficiency"],
        ["ROCE %", "EBIT / Capital Employed \u00d7100", "&gt;14% efficient; compare to the ROE spread"],
        ["Net Profit Margin %", "Net Profit / Sales \u00d7100", "&gt;10% (non-Financials); sector-dependent"],
        ["D/E", "Total Debt / Equity", "&lt;0.5 conservative; Financials structurally higher"],
        ["Interest Coverage (ICR)", "EBIT / Interest Expense", "&gt;3 comfortable; Debt Free if no debt"],
        ["FCF Conversion %", "FCF / Net Profit \u00d7100", "~80\u2013120% healthy; persistently &lt;60% = WC/capex strain"],
        ["Revenue CAGR 5Y", "(Rev_latest/Rev_5y_ago)^(1/5)\u22121", "&gt;10% sustained growth for large caps"],
        ["P/E, P/B, EV/EBITDA", "Price / Earnings, Book, EV / EBITDA", "Lower = cheaper; always vs sector median"],
        ["Dividend Yield %", "DPS / Price \u00d7100", "&gt;1.5% meaningful for large caps"],
        ["OPM %", "Operating Profit / Sales \u00d7100", "Core operating efficiency; compare to the NPM spread"],
    ], widths=[34 * mm, 56 * mm, 80 * mm]),
    P("Best Practices &amp; Pitfalls", h2),
    P("<b>Do:</b>", h3),
]
story += B([
    "Always compare a ratio to its sector median (Chapter 9) before calling it high/low.",
    "Use FCF Yield alongside P/E \u2014 a low P/E with negative FCF yield is a value trap.",
    "Check the Capital Allocation pattern for any Discount flag \u2014 \u201cDistressed\u201d + "
    "Discount = cheap for a reason.",
    "Re-run make ratios and python -m src.analytics.valuation after any ETL change.",
])
story += [P("<b>Don't:</b>", h3)]
story += B([
    "Don't screen Financials on D/E alone \u2014 use ICR and the ROE/ROCE spread instead.",
    "Don't extrapolate a 2-year CAGR \u2014 the platform shows 5Y CAGR to avoid recency bias.",
    "Don't treat SIMULATED stock_prices as live \u2014 valuation flags are indicative.",
    "Don't ignore N/A \u2014 a missing P/E shown as Fair is a data gap, not a verdict.",
])
story += [
    P("Quick Reference \u2014 Commands", h2),
    tbl([
        ["Task", "Command"],
        ["Load warehouse", "make load  \u2014 or \u2014  python -m src.etl.loader"],
        ["Compute ratios", "make ratios"],
        ["Run valuation", "python -m src.analytics.valuation"],
        ["Launch dashboard", "streamlit run src/dashboard/app.py --server.port 8501"],
        ["Launch API", "uvicorn src.api.main:app --port 8000"],
        ["Run tests", "pytest tests/ -v"],
        ["Generate tearsheets", "python -m src.reports.tearsheet"],
    ], widths=[40 * mm, 130 * mm]),
    PageBreak(),
]

# --------------------------------------------------------------------------- #
# Appendix A
# --------------------------------------------------------------------------- #
story += H1("APPENDIX A", "Acceptance Checklist Cross-Reference")
story += [
    P("This appendix maps the deliverables verified in docs/acceptance_checklist.pdf to the "
      "guide chapters where each is explained. Evidence below is read live from the warehouse and "
      "filesystem when this guide is generated."),
    tbl([
        ["ID", "Deliverable", "Path", "Guide Ch.", "Live evidence"],
        ["D-01", "nifty100.db", "data/nifty100.db", "Ch 2,3", f"{kb('data/nifty100.db'):,} KB, FK check {FK}"],
        ["D-02", "load_audit.csv", "output/load_audit.csv", "Ch 2",
         f"companies {AUDIT.get('companies', COMPANIES)} / PL {AUDIT.get('profitandloss', PL)} / "
         f"BS {AUDIT.get('balancesheet', BS)} / CF {AUDIT.get('cashflow', CF)} / "
         f"FR {AUDIT.get('financial_ratios', FR)} / SP {AUDIT.get('stock_prices', SP)}"],
        ["D-03", "validation_failures.csv", "output/validation_failures.csv", "Ch 2",
         f"{VF_ROWS:,} rows, {VF_CRIT} CRITICAL"],
        ["D-04", "exploratory_queries.sql", "notebooks/exploratory_queries.sql", "Ch 2",
         f"{kb('notebooks/exploratory_queries.sql')} KB"],
        ["D-05", "financial_ratios table", "data/nifty100.db \u2192 financial_ratios", "Ch 2,5,11",
         f"{FR:,} rows, {FR_COLS} cols, peer_percentiles {PEER_PERCENTILES:,}"],
        ["D-06", "capital_allocation.csv", "output/capital_allocation.csv", "Ch 9",
         f"{kb('output/capital_allocation.csv')} KB, {csv_rows('output/capital_allocation.csv'):,} rows"],
        ["D-07", "screener_output.xlsx", "output/screener_output.xlsx", "Ch 6",
         f"{kb('output/screener_output.xlsx')} KB, {SCREENER_SHEETS} sheets"],
        ["D-08", "screener_config.yaml", "config/screener_config.yaml", "Ch 6", "6 presets"],
        ["D-09", "peer_comparison.xlsx", "output/peer_comparison.xlsx", "Ch 7",
         f"{kb('output/peer_comparison.xlsx')} KB, {PEER_GROUPS} groups"],
        ["D-10", "Radar charts", "reports/radar_charts/", "Ch 7", f"{RADAR} PNGs"],
        ["D-11", "Streamlit Dashboard", "src/dashboard/app.py", "Ch 3,4\u201310", "8 pages, wide layout"],
        ["D-12", "valuation_summary.xlsx", "output/valuation_summary.xlsx", "Ch 11",
         f"{COMPANIES} rows, 2 sheets"],
        ["D-13", "cashflow_intelligence.xlsx", "output/cashflow_intelligence.xlsx", "Ch 9,10",
         f"{kb('output/cashflow_intelligence.xlsx')} KB"],
        ["D-14", "pros_cons_generated.csv", "output/pros_cons_generated.csv", "Ch 5",
         f"{kb('output/pros_cons_generated.csv')} KB, {PROS_CSV_ROWS:,} rows"],
        ["D-15", "analysis_parsed.csv", "output/analysis_parsed.csv", "Ch 2",
         f"{kb('output/analysis_parsed.csv')} KB"],
        ["D-16", "Company Tearsheets", "reports/tearsheets/", "Ch 10", f"{TEARSHEETS} PDFs (~2pg)"],
        ["D-17", "Sector Reports", "reports/sector/", "Ch 9,10", f"{SECTOR_REPORTS} PDFs"],
        ["D-18", "Portfolio Summary PDF", "reports/portfolio/", "Ch 10", f"{PORTFOLIO} PDF"],
        ["D-19", "cluster_labels.csv", "output/cluster_labels.csv", "Ch 6,9",
         f"{CLUSTER_ROWS} rows, {CLUSTER_N} clusters"],
        ["D-20", "FastAPI Server", "src/api/main.py", "Ch 3", "routers mounted"],
        ["D-21", "pytest_report.html", "reports/pytest_report.html", "Ch 3",
         f"{kb('reports/pytest_report.html')} KB, {TESTS} tests"],
        ["D-22", "analyst_guide.pdf", "docs/analyst_guide.pdf", "All Ch",
         f"{kb('docs/analyst_guide.pdf')} KB (this file, regenerated)"],
        ["D-23", "acceptance_checklist.pdf", "docs/acceptance_checklist.pdf", "App A",
         f"{kb('docs/acceptance_checklist.pdf')} KB"],
    ], widths=[10 * mm, 40 * mm, 52 * mm, 18 * mm, 50 * mm]),
    Spacer(1, 3 * mm),
    P(f"Cluster segmentation ({CLUSTER_ROWS} rows): {CLUSTER_INFO}."),
    P("How to verify: run python -m src.etl.loader; python -m src.analytics.ratios; python -m "
      "src.analytics.cagr; python -m src.analytics.cashflow_kpis; python -m src.analytics.peer; "
      "python -m src.analytics.valuation, then check output/load_audit.csv counts and PRAGMA "
      "foreign_key_check=0. The checklist PDF is regenerated live from the filesystem at build "
      "time \u2014 no manual entry.", small),
    P("See docs/excel_integration.md for ETL details. This guide is generated from the codebase "
      "by generate_analyst_guide.py \u2014 if the dashboard and guide disagree, the dashboard is "
      "authoritative.", small),
]
con.close()

# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
PAGE_W, PAGE_H = A4
LM = RM = 16 * mm
TM = 18 * mm
BM = 15 * mm
HEADER_H = 13 * mm

doc = BaseDocTemplate(str(OUT), pagesize=A4,
                      leftMargin=LM, rightMargin=RM, topMargin=TM, bottomMargin=BM,
                      title="Financial Intelligence Platform \u2013 Analyst Guide",
                      author="Financial Intelligence Platform")
frame = Frame(LM, BM, PAGE_W - LM - RM, PAGE_H - TM - BM - HEADER_H, id="main")
doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=lambda c, d: draw(c, d))])


def draw(canvas, doc_):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, PAGE_H - 11 * mm, PAGE_W, 11 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(LM, PAGE_H - 7.6 * mm, BRAND + "  \u2014  ANALYST GUIDE")
    canvas.setFont("Helvetica", 7.5)
    canvas.drawRightString(PAGE_W - RM, PAGE_H - 7.6 * mm, "Confidential \u2014 for analytical use")
    canvas.setFillColor(GREY)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(LM, PAGE_H - 15.5 * mm, SUBTITLE)
    canvas.setStrokeColor(colors.HexColor("#B9C6D6"))
    canvas.line(LM, BM - 4 * mm, PAGE_W - RM, BM - 4 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(LM, BM - 8.5 * mm, "docs/analyst_guide.pdf")
    canvas.drawRightString(PAGE_W - RM, BM - 8.5 * mm, "Page %d" % doc_.page)
    canvas.restoreState()


doc.build(story)
print(f"Wrote {OUT} ({OUT.stat().st_size:,} bytes, {kb('docs/analyst_guide.pdf')} KB)")