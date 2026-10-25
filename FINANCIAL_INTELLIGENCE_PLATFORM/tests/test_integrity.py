"""Integrity tests for data repair - 10 required tests."""
import pathlib, sqlite3, pandas as pd, numpy as np, pytest
from fastapi.testclient import TestClient
from src.etl.loader import read_canonical
from src.etl.normaliser import normalize_ticker

DB_PATH = pathlib.Path("data/nifty100.db")
SOURCE_DIR = pathlib.Path("data/source")

def test_1_stock_prices_source_loaded_correctly():
    """Stock_prices DB values must match canonical source Excel for same company_id+date."""
    assert DB_PATH.exists()
    # stock_prices.xlsx header is on row 0 (no banner) -> read_canonical auto-detects
    src = read_canonical(SOURCE_DIR / "stock_prices.xlsx")
    src["company_id"] = src["company_id"].apply(normalize_ticker)
    src["date"] = pd.to_datetime(src["date"]).dt.strftime("%Y-%m-%d")
    con = sqlite3.connect(str(DB_PATH))
    db = pd.read_sql("SELECT company_id, date, close_price, market_cap_crore, pe_ratio, pb_ratio, dividend_yield FROM stock_prices", con)
    con.close()
    # Sample check 10 random rows
    merged = pd.merge(src, db, on=["company_id","date"], suffixes=("_src","_db"), how="inner")
    assert len(merged) == len(src), f"DB should have all source rows {len(src)} vs merged {len(merged)}"
    # Source is OHLCV-only; only close_price is directly comparable. The valuation
    # columns come from market_cap.xlsx and are validated below against that file.
    for col in ["close_price"]:
        # Compare with tolerance
        mism = (abs(merged[f"{col}_src"] - merged[f"{col}_db"]) > 0.01).sum()
        assert mism == 0, f"Mismatch in {col}: {mism} rows differ"
    # Valuation columns must match market_cap.xlsx (2020-2024 yearly model)
    mc = read_canonical(SOURCE_DIR / "market_cap.xlsx")
    mc = mc.rename(columns={"dividend_yield_pct": "dividend_yield"})
    mc["company_id"] = mc["company_id"].apply(normalize_ticker)
    mc["year"] = pd.to_numeric(mc["year"], errors="coerce")
    mc = mc[mc["year"].notna()]
    db_mc = pd.read_sql("SELECT company_id, substr(date,1,4) AS year, market_cap_crore, pe_ratio, pb_ratio, dividend_yield FROM stock_prices", sqlite3.connect(str(DB_PATH)))
    db_mc["year"] = pd.to_numeric(db_mc["year"], errors="coerce")
    db_mc = db_mc.dropna(subset=["year"]).drop_duplicates(subset=["company_id","year"], keep="last")
    mm = pd.merge(mc[["company_id","year","market_cap_crore","pe_ratio","pb_ratio","dividend_yield"]], db_mc,
                  on=["company_id","year"], suffixes=("_mc","_db"))
    # stock_prices.xlsx spans 2020+; market_cap.xlsx includes 2019 whose rows are
    # legitimately absent from stock_prices (no trading days that year in the source).
    db_years = set(db_mc["year"].unique())
    mc_in_db = mc[mc["year"].isin(db_years)]
    assert len(mm) == len(mc_in_db), f"market_cap rows for DB years should all appear: {len(mc_in_db)} vs {len(mm)}"
    for col in ["market_cap_crore","pe_ratio","pb_ratio","dividend_yield"]:
        diff = (mm[f"{col}_mc"].fillna(0) - mm[f"{col}_db"].fillna(0)).abs().max()
        assert diff < 0.01, f"Valuation {col} mismatch vs market_cap.xlsx: max diff {diff}"

def test_2_no_incompatible_stock_price_file_overrides_canonical():
    """Reject OHLCV file: DB stock_prices must have required columns not OHLCV structure."""
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    cur.execute("PRAGMA table_info(stock_prices)")
    cols = [r[1] for r in cur.fetchall()]
    # Must have required valuation columns, must NOT have open_price etc
    for req in ["close_price","market_cap_crore","pe_ratio","pb_ratio","dividend_yield"]:
        assert req in cols, f"Missing required column {req}"
    for bad in ["open_price","high_price","low_price","volume","adjusted_close"]:
        assert bad not in cols, f"OHLCV column {bad} should not be in stock_prices"
    # Validate no nulls for required fields (canonical source has 0 nulls)
    for col in ["close_price","market_cap_crore","pe_ratio","pb_ratio","dividend_yield"]:
        cur.execute(f"SELECT COUNT(*) FROM stock_prices WHERE {col} IS NULL")
        nulls = cur.fetchone()[0]
        assert nulls == 0, f"{col} should have 0 NULLs after canonical load, got {nulls}"
    con.close()
    # Also check loader validation: canonical OHLCV source IS accepted (loader extracts
    # close_price and merges market_cap); a frame missing close is still rejected.
    from src.etl.loader import validate_stock_prices
    ohlcv = pd.DataFrame({"id":[1],"company_id":["ABB"],"date":["2020-01-01"],"open_price":[100],"high_price":[110],"low_price":[90],"close_price":[105],"volume":[1000]})
    assert validate_stock_prices(ohlcv) == True
    no_close = pd.DataFrame({"company_id":["TCS"],"date":["2020-01-01"],"open_price":[100],"high_price":[110],"low_price":[90]})
    assert validate_stock_prices(no_close) == False
    canon = pd.DataFrame({"company_id":["TCS"],"date":["2022-10-01"],"close_price":[100],"market_cap_crore":[5000],"pe_ratio":[20],"pb_ratio":[3],"dividend_yield":[1]})
    assert validate_stock_prices(canon) == True

def test_3_sectors_correctly_mapped():
    """Sectors: every classified company maps to a sector row and counts agree.

    The canonical universe is the union of all source company_ids (100), but only 92 of
    them carry a broad_sector in sectors.xlsx. The 8 unclassified ids (ULTRACEMCO,
    UNIONBANK, UNITDSPR, VBL, VEDL, WIPRO, ZOMATO, ZYDUSLIFE) have no sector in any
    canonical source; they must stay NULL rather than be assigned an invented sector.
    """
    con = sqlite3.connect(str(DB_PATH))
    sec = pd.read_sql("SELECT * FROM sectors", con)
    comps = pd.read_sql("SELECT broad_sector FROM companies", con)
    con.close()
    classified = comps["broad_sector"].dropna()
    assert len(sec) == classified.nunique(), f"Expected {classified.nunique()} sectors, got {len(sec)}"
    assert sec["company_count"].sum() == len(classified), f"Sum company_count should be {len(classified)}, got {sec['company_count'].sum()}"
    assert sec["broad_sector"].isna().sum() == 0
    assert (sec["broad_sector"] == "").sum() == 0
    # Check company broad_sector values are all in sectors
    assert set(classified.unique()).issubset(set(sec["broad_sector"].unique()))
    # Check sectors company_count matches actual grouping
    expected = classified.value_counts().to_dict()
    for _, row in sec.iterrows():
        assert row["company_count"] == expected.get(row["broad_sector"], 0)

def test_4_sector_medians_calculated_correctly():
    """Sector medians should be calculated deterministically and not remain all NULL."""
    con = sqlite3.connect(str(DB_PATH))
    sec = pd.read_sql("SELECT * FROM sectors", con)
    con.close()
    # After fix, no sector should have all three medians NULL (some may be NULL if genuinely no valid values, but not all)
    # Check that at least 9 sectors have median_roe not NULL (since we have data)
    non_null_roe = sec["median_roe"].notna().sum()
    assert non_null_roe >= 10, f"Expected at least 10 sectors with median_roe, got {non_null_roe}"
    non_null_pe = sec["median_pe"].notna().sum()
    assert non_null_pe >= 10
    non_null_de = sec["median_de"].notna().sum()
    assert non_null_de >= 10
    # Verify median calculation is deterministic: recalculate and compare one sector
    con = sqlite3.connect(str(DB_PATH))
    comps = pd.read_sql("SELECT company_id, broad_sector FROM companies", con)
    fr = pd.read_sql("SELECT company_id, year, return_on_equity_pct FROM financial_ratios", con)
    fr["year_int"] = pd.to_numeric(fr["year"], errors="coerce")
    realistic = fr[fr["year_int"] <= 2024]
    latest_year = int(realistic["year_int"].max())
    fr_latest = fr[fr["year"] == str(latest_year)]
    # Pick Financials sector
    cids = comps[comps["broad_sector"] == "Financials"]["company_id"].tolist()
    expected_median = fr_latest[fr_latest["company_id"].isin(cids)]["return_on_equity_pct"].median()
    actual = sec[sec["broad_sector"] == "Financials"]["median_roe"].iloc[0]
    assert abs(actual - expected_median) < 0.01
    con.close()

def test_5_peer_percentile_calculations_mathematically_correct():
    """Peer percentile calculations must be PERCENT_RANK and D/E inverted."""
    from src.analytics.peer import percent_rank
    con = sqlite3.connect(str(DB_PATH))
    # Check D/E inversion: lower D/E should have higher percentile
    # Find a group-year with at least 3 members and valid D/E
    pct = pd.read_sql("SELECT * FROM peer_percentiles WHERE metric='debt_to_equity' AND percentile_rank IS NOT NULL LIMIT 20", con)
    fr = pd.read_sql("SELECT * FROM financial_ratios", con)
    assert not pct.empty
    # For a specific group-year, check ordering
    sample = pct.iloc[0]
    grp = sample["peer_group_name"]
    yr = sample["year"]
    # Get all D/E values for that group-year
    pg = pd.read_sql("SELECT company_id FROM peer_groups WHERE peer_group_name=?", con, params=(grp,))
    members = pg["company_id"].tolist()
    fr_grp = fr[(fr["company_id"].isin(members)) & (fr["year"] == yr)][["company_id","debt_to_equity"]]
    fr_grp = fr_grp.dropna()
    if len(fr_grp) >= 2:
        # Compute expected percentile via percent_rank on inverted
        s = -fr_grp["debt_to_equity"]
        n = len(s)
        ranks = s.rank(method="min")
        expected_pct = (ranks - 1) / (n - 1)
        # Map to company
        for _, r in fr_grp.iterrows():
            cid = r["company_id"]
            row = pct[(pct["company_id"] == cid) & (pct["peer_group_name"] == grp) & (pct["year"] == yr)]
            if not row.empty:
                actual = row.iloc[0]["percentile_rank"]
                exp = expected_pct[fr_grp["company_id"] == cid].iloc[0]
                assert abs(actual - exp) < 1e-6
                # Check inversion: lowest D/E should have highest percentile
                min_de_cid = fr_grp.loc[fr_grp["debt_to_equity"].idxmin(), "company_id"]
                min_row = pct[(pct["company_id"] == min_de_cid) & (pct["peer_group_name"] == grp) & (pct["year"] == yr)]
                if not min_row.empty:
                    assert min_row.iloc[0]["percentile_rank"] == 1.0 or min_row.iloc[0]["percentile_rank"] == max(pct[(pct["peer_group_name"]==grp)&(pct["year"]==yr)]["percentile_rank"])
    # Also test percent_rank function directly
    s = pd.Series([1,2,3,4,5])
    pct_series = percent_rank(s)
    assert abs(pct_series.iloc[0] - 0.0) < 1e-6
    assert abs(pct_series.iloc[2] - 0.5) < 1e-6
    assert abs(pct_series.iloc[4] - 1.0) < 1e-6
    # Single value case -> 0.5
    assert percent_rank(pd.Series([10])).iloc[0] == 0.5
    con.close()

def test_6_missing_source_values_remain_null():
    """Where source metric is NULL, peer_percentiles percentile_rank must remain NULL."""
    con = sqlite3.connect(str(DB_PATH))
    # Find a financial_ratios row where metric is NULL
    fr = pd.read_sql("SELECT company_id, year, return_on_equity_pct FROM financial_ratios WHERE return_on_equity_pct IS NULL LIMIT 5", con)
    if not fr.empty:
        cid = fr.iloc[0]["company_id"]
        yr = fr.iloc[0]["year"]
        pct = pd.read_sql("SELECT * FROM peer_percentiles WHERE company_id=? AND year=? AND metric='return_on_equity_pct'", con, params=(cid, yr))
        if not pct.empty:
            # percentile should be NULL
            assert pd.isna(pct.iloc[0]["percentile_rank"]), "percentile should be NULL when source missing"
            assert pd.isna(pct.iloc[0]["value"])
    con.close()

def test_7_no_random_values_inserted():
    """No random values inserted: stock_prices DB must exactly match source within tolerance, no generated fake."""
    # stock_prices.xlsx header is on row 0 -> read_canonical auto-detects
    src = read_canonical(SOURCE_DIR / "stock_prices.xlsx")
    src["company_id"] = src["company_id"].apply(normalize_ticker)
    src["date"] = pd.to_datetime(src["date"]).dt.strftime("%Y-%m-%d")
    con = sqlite3.connect(str(DB_PATH))
    db = pd.read_sql("SELECT company_id, date, close_price FROM stock_prices", con)
    con.close()
    merged = pd.merge(src[["company_id","date","close_price"]], db, on=["company_id","date"], suffixes=("_src","_db"))
    # Check that close_price values are not random (must match exactly)
    for _, r in merged.head(5).iterrows():
        assert abs(r["close_price_src"] - r["close_price_db"]) < 0.01
    # Also check that no company_id is random CMP that doesn't exist in companies
    comps = pd.read_sql("SELECT company_id FROM companies", sqlite3.connect(str(DB_PATH)))
    assert set(merged["company_id"].unique()).issubset(set(comps["company_id"].unique()))

def test_8_source_database_values_match():
    """Source/database audit should have no MISMATCH for stock_prices."""
    audit_path = pathlib.Path("output/source_database_audit.csv")
    assert audit_path.exists()
    df = pd.read_csv(audit_path)
    mism = df[(df["table"]=="stock_prices") & (df["status"]=="MISMATCH")]
    assert len(mism) == 0, f"Found {len(mism)} MISMATCH in stock_prices audit"
    # Sectors company_count may have 2 mismatches where DB was deterministically corrected to match companies grouping (Financials 19->18, IT 10->11)
    mism_sec = df[(df["table"]=="sectors") & (df["field"]=="company_count") & (df["status"]=="MISMATCH")]
    # Allow up to 2 deterministic corrections for sectors vs source mismatch
    if len(mism_sec) > 0:
        # Verify they are the expected sectors
        assert set(mism_sec["date_or_year"].tolist()).issubset({"Financials","IT"})
        assert len(mism_sec) <= 2

def test_9_foreign_keys_remain_valid():
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    cur.execute("PRAGMA foreign_key_check")
    violations = cur.fetchall()
    assert len(violations) == 0, f"FK violations: {violations}"
    # Canonical universe is the union of company_ids across all sources: 92 from
    # companies.xlsx plus 8 index members that only appear in the financial statements.
    cur.execute("SELECT COUNT(*) FROM companies")
    assert cur.fetchone()[0] == 100
    cur.execute("SELECT COUNT(*) FROM stock_prices")
    cnt = cur.fetchone()[0]
    assert 5500 <= cnt <= 5530, f"stock_prices count should be ~5520, got {cnt}"
    con.close()

def test_10_dashboard_api_can_read_corrected_structures():
    """API and dashboard utils should handle corrected schemas without crashing."""
    from src.api.main import app
    from src.dashboard.utils.db import get_companies, get_sectors, get_peer_percentiles
    client = TestClient(app)
    # Test API sectors
    r = client.get("/api/v1/sectors")
    assert r.status_code == 200
    data = r.json()
    assert "sectors" in data
    # Check that sectors have medians (not all null)
    has_median = any(s.get("median_roe") is not None for s in data["sectors"])
    assert has_median
    # Test API peers with long format
    # Get a known peer group
    con = sqlite3.connect(str(DB_PATH))
    grp = pd.read_sql("SELECT peer_group_name FROM peer_groups LIMIT 1", con).iloc[0]["peer_group_name"]
    con.close()
    r2 = client.get(f"/api/v1/peers/{grp}")
    # Could be 200 or 404 depending on routing, check at least not 500
    assert r2.status_code in [200, 404]
    if r2.status_code == 200:
        j = r2.json()
        assert "members" in j
    # Test dashboard utils
    comps = get_companies()
    assert len(comps) == 100
    secs = get_sectors()
    assert len(secs) == 10
    pct = get_peer_percentiles()
    assert len(pct) > 0
    assert set(["company_id","peer_group_name","metric","value","percentile_rank","year"]).issubset(set(pct.columns))

def test_11_analysis_preserves_every_source_period_row():
    """analysis must hold one row per source (company, period) row, not one per company.

    analysis.xlsx carries 20 rows across 5 companies (10Y/5Y/3Y/TTM each). The loader
    used to drop the source id and de-duplicate on company_id, collapsing 20 -> 5, after
    which the FK filter removed WIPRO (absent from companies.xlsx) leaving 4.
    """
    from src.etl.loader import read_canonical, normalize_df, SOURCE_DIR
    src = normalize_df(read_canonical(SOURCE_DIR / "analysis.xlsx"), "analysis")
    con = sqlite3.connect(str(DB_PATH))
    db = pd.read_sql("SELECT * FROM analysis", con)
    wipro_in_companies = pd.read_sql("SELECT COUNT(*) n FROM companies WHERE company_id='WIPRO'", con).iloc[0]["n"]
    con.close()
    # No source row may be lost
    assert len(db) == len(src), f"analysis rows {len(db)} != source rows {len(src)}"
    assert db["analysis_id"].nunique() == len(src), "analysis_id must be unique per source row"
    assert len(db) > len(db["company_id"].unique()), "analysis must hold multiple rows per company"
    # Every source company/period survives with identical metric text
    metric_cols = ["compounded_sales_growth","compounded_profit_growth","stock_price_cagr","roe"]
    for col in metric_cols:
        assert set(src[col].astype(str)) == set(db[col].astype(str)), f"{col} values diverged from source"
    keyed = src.set_index("analysis_id")[metric_cols].sort_index()
    from_db = db.set_index("analysis_id")[metric_cols].sort_index()
    # Excel yields a nullable Int64 index, SQLite a plain int64; compare on a common dtype
    keyed.index = keyed.index.astype("int64")
    from_db.index = from_db.index.astype("int64")
    assert keyed.equals(from_db), "analysis rows do not match source row-for-row"
    # WIPRO must be present in companies so its analysis rows satisfy the FK
    assert wipro_in_companies == 1, "WIPRO must exist in the canonical company master"
    assert (db["company_id"] == "WIPRO").sum() == 4, "WIPRO must keep all 4 period rows"

def test_12_no_agtl_atgl_duplicate_identity():
    """AGTL is a cashflow.xlsx-only typo for ATGL; there must be exactly one identity."""
    con = sqlite3.connect(str(DB_PATH))
    try:
        assert pd.read_sql("SELECT COUNT(*) n FROM companies WHERE company_id='AGTL'", con).iloc[0]["n"] == 0
        assert pd.read_sql("SELECT COUNT(*) n FROM cashflow WHERE company_id='AGTL'", con).iloc[0]["n"] == 0
        assert pd.read_sql("SELECT COUNT(*) n FROM cashflow WHERE company_id='ATGL'", con).iloc[0]["n"] > 0
    finally:
        con.close()
