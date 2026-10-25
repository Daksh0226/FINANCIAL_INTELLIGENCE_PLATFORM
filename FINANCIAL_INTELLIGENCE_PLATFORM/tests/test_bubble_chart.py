import pathlib, sqlite3, pandas as pd, pytest

DB = pathlib.Path("data/nifty100.db")

# Canonical 10-sector taxonomy (README "Company Universe" / sectors table)
CANONICAL_SECTORS = [
    "Communication Services",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "Financials",
    "Healthcare",
    "Industrials",
    "Information Technology",
    "Materials",
    "Real Estate",
]

def test_sector_chart_year_filter():
    from src.dashboard.utils.db import get_bubble_chart_data
    # Materials has 9 companies in both 2019 and 2024 (stable sector for this check)
    df19 = get_bubble_chart_data(2019, "Materials")
    df24 = get_bubble_chart_data(2024, "Materials")
    # Each should have year column matching requested year
    assert (df19["year"] == "2019").all()
    assert (df24["year"] == "2024").all()
    # Should have 9 each for Materials (per DB)
    assert len(df19) == 9
    assert len(df24) == 9

def test_sector_chart_no_duplicate_company_year():
    from src.dashboard.utils.db import get_bubble_chart_data
    for yr in [2019,2024]:
        for sector in ["Consumer Staples","Information Technology","Financials"]:
            df = get_bubble_chart_data(yr, sector)
            dup = df.duplicated(subset=["company_id","year"]).sum()
            assert dup == 0, f"Duplicate for {yr} {sector}"

def test_sector_chart_revenue_matches_year():
    from src.dashboard.utils.db import get_bubble_chart_data
    con = sqlite3.connect(str(DB))
    for yr in [2019,2024]:
        df = get_bubble_chart_data(yr, "Consumer Staples")
        pl = pd.read_sql("SELECT company_id, sales FROM profitandloss WHERE year=?", con, params=[str(yr)])
        merged = pd.merge(df[["company_id","revenue"]], pl, on="company_id", how="left")
        # revenue should equal sales for that year
        mism = (merged["revenue"] != merged["sales"]).sum()
        # Allow NaN equality
        mism = ((merged["revenue"].fillna(-1) != merged["sales"].fillna(-1))).sum()
        assert mism == 0, f"Revenue mismatch for {yr}"
    con.close()

def test_sector_chart_roe_matches_year():
    from src.dashboard.utils.db import get_bubble_chart_data
    con = sqlite3.connect(str(DB))
    for yr in [2019,2024]:
        df = get_bubble_chart_data(yr, "Consumer Staples")
        fr = pd.read_sql("SELECT company_id, return_on_equity_pct FROM financial_ratios WHERE year=?", con, params=[str(yr)])
        merged = pd.merge(df[["company_id","roe"]], fr, left_on="company_id", right_on="company_id", how="left")
        # roe should equal return_on_equity_pct
        mism = ((merged["roe"].fillna(-999) != merged["return_on_equity_pct"].fillna(-999))).sum()
        assert mism == 0, f"ROE mismatch for {yr}"
    con.close()

def test_sector_chart_market_cap_matches_year():
    from src.dashboard.utils.db import get_bubble_chart_data
    con = sqlite3.connect(str(DB))
    for yr in [2019,2024]:
        df = get_bubble_chart_data(yr, "Consumer Staples")
        # Get market cap for that year: latest within year
        sp = pd.read_sql("SELECT company_id, date, market_cap_crore FROM stock_prices WHERE substr(date,1,4)=?", con, params=[str(yr)])
        sp["date"] = pd.to_datetime(sp["date"])
        sp_latest = sp.sort_values("date").groupby("company_id").tail(1)[["company_id","market_cap_crore"]]
        merged = pd.merge(df[["company_id","market_cap"]], sp_latest, on="company_id", how="left")
        # market_cap should equal market_cap_crore for that year
        # Allow small float tolerance
        if not merged.empty:
            diff = (merged["market_cap"] - merged["market_cap_crore"]).abs().fillna(0).max()
            assert diff < 0.01, f"Market cap mismatch for {yr} diff {diff}"
    con.close()

def test_sector_chart_switching_year():
    from src.dashboard.utils.db import get_bubble_chart_data
    df19 = get_bubble_chart_data(2019, "Consumer Staples")
    df24 = get_bubble_chart_data(2024, "Consumer Staples")
    # Revenue should change per year (check at least one company)
    # For CMP030, revenue 2019 79307 vs 2024 85064 (from earlier audit)
    r19 = df19[df19["company_id"]=="CMP030"]["revenue"].values[0] if "CMP030" in df19["company_id"].values else None
    r24 = df24[df24["company_id"]=="CMP030"]["revenue"].values[0] if "CMP030" in df24["company_id"].values else None
    if r19 and r24:
        assert r19 != r24, "Revenue should change per year for same company"
    # ROE should also change
    roe19 = df19[df19["company_id"]=="CMP030"]["roe"].values[0] if "CMP030" in df19["company_id"].values else None
    roe24 = df24[df24["company_id"]=="CMP030"]["roe"].values[0] if "CMP030" in df24["company_id"].values else None
    if roe19 and roe24:
        assert roe19 != roe24

def test_sector_chart_no_cartesian_join():
    from src.dashboard.utils.db import get_bubble_chart_data
    # For Materials 2024, should be 9 rows, not 9*9 or 9*92
    df = get_bubble_chart_data(2024, "Materials")
    assert len(df) == 9
    assert len(df) < 20  # Not Cartesian
    # Check total for all sectors 2024 should be 92, not 92*92
    df_all = get_bubble_chart_data(2024, None)
    assert len(df_all) == 92
    assert len(df_all) < 200

def test_sector_chart_no_double_percentage():
    from src.dashboard.utils.db import get_bubble_chart_data
    df = get_bubble_chart_data(2024, "Materials")
    # ROE stored as 15 means 15%, should not be 1500
    assert df["roe"].max() < 500, f"ROE max {df['roe'].max()} suggests double conversion"
    assert df["roe"].min() > -100

def test_sector_chart_sector_filter():
    from src.dashboard.utils.db import get_bubble_chart_data
    df = get_bubble_chart_data(2024, "Information Technology")
    assert (df["broad_sector"] == "Information Technology").all()
    assert len(df) == 5  # Information Technology has 5 companies

def test_sector_chart_all_sectors():
    from src.dashboard.utils.db import get_bubble_chart_data
    for sector in CANONICAL_SECTORS:
        df = get_bubble_chart_data(2024, sector)
        assert not df.empty, f"Empty for {sector}"
        assert df["broad_sector"].nunique() == 1
        assert df["broad_sector"].iloc[0] == sector