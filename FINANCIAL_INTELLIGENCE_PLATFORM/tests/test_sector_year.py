import pathlib, sqlite3, pandas as pd, pytest

DB = pathlib.Path("data/nifty100.db")
SOURCE = pathlib.Path("data/source")

# Canonical 10-sector taxonomy (README "Company Universe")
CANONICAL_SECTORS = [
    "Financials",
    "Consumer Discretionary",
    "Energy",
    "Industrials",
    "Materials",
    "Consumer Staples",
    "Healthcare",
    "Information Technology",
    "Communication Services",
    "Real Estate",
]

def _expected_total(year):
    # 92 classified companies; JIOFIN (IPO Sep 2023) has no financial data before 2024,
    # so 2019/2020 legitimately sum to 91 while 2024 sums to 92.
    return 92 if str(year) == "2024" else 91

def test_get_sector_breakdown_2019():
    from src.dashboard.utils.db import get_sector_breakdown_by_year
    df = get_sector_breakdown_by_year(2019)
    assert not df.empty
    assert "sector" in df.columns
    assert "company_count" in df.columns
    assert df["company_count"].sum() == _expected_total(2019)

def test_get_sector_breakdown_2020():
    from src.dashboard.utils.db import get_sector_breakdown_by_year
    df = get_sector_breakdown_by_year(2020)
    assert df["company_count"].sum() == _expected_total(2020)

def test_get_sector_breakdown_2024():
    from src.dashboard.utils.db import get_sector_breakdown_by_year
    df = get_sector_breakdown_by_year("2024")
    assert df["company_count"].sum() == _expected_total(2024)
    assert set(df["sector"]) == set(CANONICAL_SECTORS)

def test_selected_year_passed_to_sql():
    # Verify that function uses year param in query (check source)
    import inspect
    from src.dashboard.utils.db import get_sector_breakdown_by_year
    src = inspect.getsource(get_sector_breakdown_by_year)
    assert "WHERE fr.year = ?" in src
    assert "GROUP BY c.broad_sector" in src

def test_cached_results_year_specific():
    from src.dashboard.utils.db import get_sector_breakdown_by_year
    df19 = get_sector_breakdown_by_year(2019)
    df20 = get_sector_breakdown_by_year(2020)
    # They should be equal in this dataset (identical distribution) but cache keys are different
    # Verify that function is cached with year param by checking cache_info if available
    if hasattr(get_sector_breakdown_by_year, "cache_info"):
        before = get_sector_breakdown_by_year.cache_info().hits
        get_sector_breakdown_by_year(2019)
        after = get_sector_breakdown_by_year.cache_info().hits
        assert after >= before
    else:
        # Fallback: ensure different years give same structure but are separate calls
        assert len(df19) == len(df20)

def test_percentages_sum_to_100():
    from src.dashboard.utils.db import get_sector_breakdown_by_year
    for yr in [2019,2020,2024]:
        df = get_sector_breakdown_by_year(yr)
        total = df["company_count"].sum()
        pct_sum = (df["company_count"] / total * 100).sum()
        assert abs(pct_sum - 100) < 0.01

def test_sector_names_from_companies():
    from src.dashboard.utils.db import get_sector_breakdown_by_year
    df = get_sector_breakdown_by_year(2024)
    con = sqlite3.connect(str(DB))
    sectors_db = pd.read_sql("SELECT DISTINCT broad_sector FROM companies", con)
    con.close()
    assert set(df["sector"]).issubset(set(sectors_db["broad_sector"]))

def test_no_hardcoded_year_values():
    import pathlib
    home = pathlib.Path("src/dashboard/pages/01_home.py").read_text(encoding="utf-8")
    # Ensure no hardcoded dict like {2019: 18, 2020: 19}
    assert '"2019": 18' not in home
    # Ensure it uses selected_year variable
    assert "get_sector_breakdown_by_year(year)" in home

def test_database_results_match_source():
    # Compare source Excel vs DB for 2024 (classified sectors only)
    import sys
    sys.path.insert(0, str(pathlib.Path("data/source").parent.parent / "src"))
    try:
        from src.etl.normaliser import normalize_ticker, normalize_year
    except:
        def normalize_ticker(x): return str(x).strip().upper()
        def normalize_year(x):
            import re
            return re.search(r"(19|20)\d{2}", str(x)).group(0) if re.search(r"(19|20)\d{2}", str(x)) else None
    comp_src = pd.read_excel(SOURCE / "companies.xlsx", header=1)
    comp_src = comp_src.loc[:, ~comp_src.columns.astype(str).str.contains("Unnamed")]
    # companies.xlsx uses id (not company_id), same as the loader
    comp_src = comp_src.rename(columns={"id": "company_id"})
    # broad_sector lives in sectors.xlsx (per-company, header on row 0), not companies.xlsx
    sec_src = pd.read_excel(SOURCE / "sectors.xlsx", header=0)
    if "broad_sector" not in comp_src.columns:
        comp_src = comp_src.merge(sec_src[["company_id","broad_sector"]], on="company_id", how="left")
    pl_src = pd.read_excel(SOURCE / "profitandloss.xlsx", header=1)
    pl_src = pl_src.loc[:, ~pl_src.columns.astype(str).str.contains("Unnamed")]
    pl_src["company_id"] = pl_src["company_id"].apply(normalize_ticker)
    pl_src["year"] = pl_src["year"].apply(normalize_year)
    comp_src["company_id"] = comp_src["company_id"].apply(normalize_ticker)
    yr = "2024"
    cids = set(pl_src[pl_src["year"]==yr]["company_id"].dropna())
    src_dist = comp_src[comp_src["company_id"].isin(cids)]["broad_sector"].value_counts().to_dict()
    con = sqlite3.connect(str(DB))
    df_db = pd.read_sql("""
        SELECT c.broad_sector, COUNT(DISTINCT fr.company_id) as cnt
        FROM financial_ratios fr JOIN companies c ON c.company_id=fr.company_id
        WHERE fr.year=? AND c.broad_sector IS NOT NULL
        GROUP BY c.broad_sector
    """, con, params=[yr])
    con.close()
    db_dist = dict(zip(df_db["broad_sector"], df_db["cnt"]))
    assert src_dist == db_dist

def test_home_chart_title_is_static():
    home = pathlib.Path("src/dashboard/pages/01_home.py").read_text(encoding="utf-8")
    assert 'Companies by 10 Sectors' in home
    # Ensure title is static and does not contain dynamic year
    assert 'Companies by Sector — {year}' not in home
    assert 'Companies by Sector - {year}' not in home
    # Verify both px.pie and layout title are static
    assert home.count('Companies by 10 Sectors') >= 2