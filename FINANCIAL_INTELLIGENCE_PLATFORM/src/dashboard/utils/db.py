"""Shared data loader for Streamlit dashboard — cached @st.cache_data(ttl=600) on every query."""
import pathlib
import sqlite3

import pandas as pd
import streamlit as st

# Resolve DB path robustly from any cwd (streamlit may run from project root or src/dashboard)
_CANDIDATES = [
    pathlib.Path("data/nifty100.db"),
    pathlib.Path(__file__).resolve().parents[3] / "data" / "nifty100.db",
    pathlib.Path(__file__).resolve().parents[4] / "data" / "nifty100.db",
    pathlib.Path.cwd() / "data" / "nifty100.db",
]
DB_PATH = next((p for p in _CANDIDATES if p.exists()), pathlib.Path("data/nifty100.db"))


def _conn():
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


# ---------------------------------------------------------------------------
# Spec-required function signatures (all cached)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600)
def get_companies():
    """Return all companies."""
    con = _conn()
    df = pd.read_sql("SELECT * FROM companies", con)
    con.close()
    return df


@st.cache_data(ttl=600)
def get_ratios(ticker=None, year=None):
    """Return financial_ratios filtered by ticker and/or year if supplied."""
    con = _conn()
    if ticker is None and year is None:
        df = pd.read_sql("SELECT * FROM financial_ratios", con)
    else:
        query = "SELECT * FROM financial_ratios WHERE 1=1"
        params = []
        if ticker is not None:
            query += " AND company_id = ?"
            params.append(ticker)
        if year is not None:
            query += " AND year = ?"
            params.append(str(year))
        df = pd.read_sql(query, con, params=params)
    con.close()
    return df


@st.cache_data(ttl=600)
def get_pl(ticker=None):
    """Return profitandloss, optionally filtered by ticker."""
    con = _conn()
    if ticker is None:
        df = pd.read_sql("SELECT * FROM profitandloss", con)
    else:
        df = pd.read_sql("SELECT * FROM profitandloss WHERE company_id = ?", con, params=(ticker,))
    con.close()
    return df


@st.cache_data(ttl=600)
def get_bs(ticker=None):
    """Return balancesheet, optionally filtered by ticker."""
    con = _conn()
    if ticker is None:
        df = pd.read_sql("SELECT * FROM balancesheet", con)
    else:
        df = pd.read_sql("SELECT * FROM balancesheet WHERE company_id = ?", con, params=(ticker,))
    con.close()
    return df


@st.cache_data(ttl=600)
def get_cf(ticker=None):
    """Return cashflow, optionally filtered by ticker."""
    con = _conn()
    if ticker is None:
        df = pd.read_sql("SELECT * FROM cashflow", con)
    else:
        df = pd.read_sql("SELECT * FROM cashflow WHERE company_id = ?", con, params=(ticker,))
    con.close()
    return df


@st.cache_data(ttl=600)
def get_sectors():
    """Return sectors with calculated medians (prefer sectors table)."""
    con = _conn()
    df = pd.read_sql("SELECT * FROM sectors", con)
    # If table empty, derive from companies
    if df.empty:
        companies = pd.read_sql("SELECT broad_sector FROM companies", con)
        counts = companies["broad_sector"].value_counts().reset_index()
        counts.columns = ["broad_sector", "company_count"]
        counts["median_roe"] = None
        counts["median_pe"] = None
        counts["median_de"] = None
        df = counts
    else:
        # Ensure medians are present; if all NULL, keep as is (calculated values may be NULL legitimately)
        # But ensure company_count matches actual companies count
        companies = pd.read_sql("SELECT broad_sector FROM companies", con)
        actual_counts = companies["broad_sector"].value_counts().to_dict()
        for idx, row in df.iterrows():
            sector = row["broad_sector"]
            if sector in actual_counts and row["company_count"] != actual_counts[sector]:
                df.at[idx, "company_count"] = actual_counts[sector]
    con.close()
    return df

@st.cache_data(ttl=600)
def get_sector_breakdown_by_year(year):
    """Year-aware sector breakdown for Home page donut.
    Uses financial_ratios (canonical year-specific) joined to companies.
    year is part of cache key so 2024 vs 2023 do not share cache.
    """
    con = _conn()
    # Canonical: COUNT DISTINCT company_id with valid financial_ratios for that year, grouped by broad_sector
    # financial_ratios is outer merge of PL+BS+CF, so presence indicates company had data that year
    # NULL-sector companies (8 promoted index members) are deliberately excluded: they have no sector.
    query = """
        SELECT
            c.broad_sector AS sector,
            COUNT(DISTINCT c.company_id) AS company_count
        FROM companies c
        JOIN financial_ratios fr ON fr.company_id = c.company_id
        WHERE fr.year = ? AND c.broad_sector IS NOT NULL
        GROUP BY c.broad_sector
        ORDER BY company_count DESC, sector ASC
    """
    try:
        df = pd.read_sql(query, con, params=[str(year)])
    except Exception:
        df = pd.DataFrame(columns=["sector", "company_count"])
    con.close()
    # If no data for that year, return empty (caller will show "No sector data available")
    return df


@st.cache_data(ttl=600)
def get_bubble_chart_data(year, sector=None):
    """Year-aware bubble chart data: one row per company/year.
    Correct pipeline: filter year BEFORE joins, avoid Cartesian joins,
    validate one row per company/year, correct ROE (stored as %), revenue and market_cap per selected year.
    Cached with year + sector.
    """
    con = _conn()
    # Validate year
    try:
        year_str = str(int(year))
    except:
        year_str = str(year)
    # Year-filtered subqueries - each 1 row per company for that year
    # Companies (static sector info) — skip the 8 promoted NULL-sector members
    companies = pd.read_sql("SELECT company_id, company_name, broad_sector, sub_sector FROM companies", con)
    companies = companies[companies["broad_sector"].notna()]
    if sector:
        companies = companies[companies["broad_sector"] == sector]
    # Financial ratios for ROE (year-specific)
    fr = pd.read_sql("SELECT company_id, year, return_on_equity_pct FROM financial_ratios WHERE year = ?", con, params=[year_str])
    # Profitandloss for revenue (year-specific)
    pl = pd.read_sql("SELECT company_id, year, sales FROM profitandloss WHERE year = ?", con, params=[year_str])
    # Stock prices for market cap: latest market cap within that year
    # Use substr(date,1,4) = year and pick max date per company
    sp_raw = pd.read_sql("SELECT company_id, date, market_cap_crore FROM stock_prices WHERE substr(date,1,4) = ?", con, params=[year_str])
    if not sp_raw.empty:
        sp_raw["date"] = pd.to_datetime(sp_raw["date"], errors="coerce")
        sp = sp_raw.sort_values("date").groupby("company_id").tail(1)[["company_id","market_cap_crore"]]
    else:
        sp = pd.DataFrame(columns=["company_id","market_cap_crore"])
    # Join: companies left join fr, pl, sp - each is 1 row per company, so result is 1 row per company
    df = companies.copy()
    # Merge with year-specific data
    df = pd.merge(df, fr[["company_id","return_on_equity_pct"]], on="company_id", how="inner")  # inner to only keep companies with data for that year
    df = pd.merge(df, pl[["company_id","sales"]], on="company_id", how="left")
    df = pd.merge(df, sp, on="company_id", how="left")
    # Add year column
    df["year"] = year_str
    # Validation
    # Check for duplicates
    dup = df.duplicated(subset=["company_id","year"]).sum()
    if dup > 0:
        # Fix by deduplicating, but log
        df = df.drop_duplicates(subset=["company_id","year"])
    # Check ROE not double-converted: stored as 15 means 15%, should be displayed as 15, not 1500
    # We keep as is, do not multiply by 100
    # Validate numeric
    df["revenue"] = pd.to_numeric(df["sales"], errors="coerce")
    df["roe"] = pd.to_numeric(df["return_on_equity_pct"], errors="coerce")
    df["market_cap"] = pd.to_numeric(df["market_cap_crore"], errors="coerce")
    # Filter to valid chart observations: company_id, broad_sector, sub_sector, year present, revenue>=0, market_cap>=0
    # Keep rows where revenue, roe, market_cap are numeric (allow NaN for now, caller will filter for bubble)
    con.close()
    return df

def validate_chart_dataset(df, year, sector):
    """Debug validation for bubble chart dataset."""
    result = {
        "selected_year": year,
        "selected_sector": sector,
        "rows_returned": len(df),
        "unique_companies": df["company_id"].nunique() if not df.empty and "company_id" in df.columns else 0,
        "duplicate_company_year": int(df.duplicated(subset=["company_id","year"]).sum()) if not df.empty and "company_id" in df.columns and "year" in df.columns else 0,
        "missing_revenue": int(df["revenue"].isna().sum()) if "revenue" in df.columns else 0,
        "missing_roe": int(df["roe"].isna().sum()) if "roe" in df.columns else 0,
        "missing_market_cap": int(df["market_cap"].isna().sum()) if "market_cap" in df.columns else 0,
        "min_roe": float(df["roe"].min()) if not df.empty and "roe" in df.columns and df["roe"].notna().any() else None,
        "max_roe": float(df["roe"].max()) if not df.empty and "roe" in df.columns and df["roe"].notna().any() else None,
        "min_revenue": float(df["revenue"].min()) if not df.empty and "revenue" in df.columns and df["revenue"].notna().any() else None,
        "max_revenue": float(df["revenue"].max()) if not df.empty and "revenue" in df.columns and df["revenue"].notna().any() else None,
        "min_market_cap": float(df["market_cap"].min()) if not df.empty and "market_cap" in df.columns and df["market_cap"].notna().any() else None,
        "max_market_cap": float(df["market_cap"].max()) if not df.empty and "market_cap" in df.columns and df["market_cap"].notna().any() else None,
    }
    return result


@st.cache_data(ttl=600)
def get_peer_percentiles(company_id=None, peer_group_name=None, year=None):
    """Return peer_percentiles in long format (canonical)."""
    con = _conn()
    query = "SELECT * FROM peer_percentiles WHERE 1=1"
    params = []
    if company_id:
        query += " AND company_id=?"
        params.append(company_id)
    if peer_group_name:
        query += " AND peer_group_name=?"
        params.append(peer_group_name)
    if year:
        query += " AND year=?"
        params.append(str(year))
    df = pd.read_sql(query, con, params=params)
    con.close()
    return df


@st.cache_data(ttl=600)
def get_peers(group_name=None):
    """Return peer_groups (and join company names). If group_name supplied, filter."""
    con = _conn()
    if group_name is None:
        df = pd.read_sql("SELECT * FROM peer_groups", con)
    else:
        df = pd.read_sql("SELECT * FROM peer_groups WHERE peer_group_name = ?", con, params=(group_name,))
    # enrich with company_name for display
    try:
        comps = pd.read_sql("SELECT company_id, company_name, broad_sector FROM companies", con)
        df = df.merge(comps, on="company_id", how="left")
    except Exception:
        pass
    con.close()
    return df


@st.cache_data(ttl=600)
def get_valuation(ticker=None):
    """Return valuation view: latest FCF, market cap, P/E, P/B, EV/EBITDA, FCF yield.

    If ticker supplied, filter to that company.
    Falls back to reading output/valuation_summary.xlsx if DB tables incomplete.
    """
    con = _conn()
    try:
        # Prefer market_cap.xlsx-derived stock_prices / market_cap
        companies = pd.read_sql("SELECT company_id, company_name, broad_sector FROM companies", con)
        fr = pd.read_sql("SELECT company_id, year, free_cash_flow_cr FROM financial_ratios", con)
        sp = pd.read_sql("SELECT company_id, date, close_price, market_cap_crore, pe_ratio, pb_ratio FROM stock_prices", con)
        # Try market_cap.xlsx directly for EV/EBITDA if exists as source
        ev_map = {}
        mc_path = pathlib.Path("data/source/market_cap.xlsx")
        if not mc_path.exists():
            mc_path = pathlib.Path(__file__).resolve().parents[3] / "data" / "source" / "market_cap.xlsx"
        if mc_path.exists():
            import openpyxl  # noqa
            mc_df = pd.read_excel(mc_path)
            # latest per company
            mc_df["year"] = pd.to_numeric(mc_df["year"], errors="coerce")
            latest_mc = mc_df.sort_values("year").groupby("company_id").tail(1)
            ev_map = dict(zip(latest_mc["company_id"], latest_mc.get("ev_ebitda", pd.Series())))
        # latest FR
        fr["year_int"] = pd.to_numeric(fr["year"], errors="coerce")
        latest_fr = fr.sort_values("year_int").groupby("company_id").tail(1)
        # latest SP
        sp["date"] = pd.to_datetime(sp["date"], errors="coerce")
        latest_sp = sp.sort_values("date").groupby("company_id").tail(1)
        df = pd.merge(latest_fr[["company_id", "year", "free_cash_flow_cr"]], latest_sp, on="company_id", how="left")
        df = pd.merge(companies, df, on="company_id", how="left")
        # FCF yield
        import numpy as np
        df["FCF_yield_pct"] = np.where(df["market_cap_crore"] > 0, df["free_cash_flow_cr"] / df["market_cap_crore"] * 100, float("nan"))
        df["EV_EBITDA"] = df["company_id"].map(ev_map)
        # tidy column names to spec where possible
        df.rename(columns={"pe_ratio": "P/E", "pb_ratio": "P/B", "broad_sector": "sector", "company_name": "company_name"}, inplace=True)
        if ticker:
            df = df[df["company_id"] == ticker]
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()
    # Fallback to xlsx if DF empty
    if df.empty:
        xlsx = pathlib.Path("output/valuation_summary.xlsx")
        if not xlsx.exists():
            xlsx = pathlib.Path(__file__).resolve().parents[3] / "output" / "valuation_summary.xlsx"
        if xlsx.exists():
            try:
                df = pd.read_excel(xlsx, sheet_name=0)
                if ticker:
                    df = df[df["company_id"] == ticker]
            except Exception:
                pass
    return df
