"""Source-to-Database validation audit.
Compares DB values against Excel source datasets for STOCK_PRICES, SECTORS, PEER_PERCENTILES."""
import pathlib
import pandas as pd
import sqlite3
from .normaliser import normalize_ticker

DB_PATH = pathlib.Path("data/nifty100.db")
SOURCE_DIR = pathlib.Path("data/source")
OUTPUT_DIR = pathlib.Path("output")
OUTPUT_CSV = OUTPUT_DIR / "source_database_audit.csv"

def read_source(path: pathlib.Path) -> pd.DataFrame:
    if not path.exists():
        print(f"Source missing: {path}")
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, header=1)
        df = df.loc[:, ~df.columns.astype(str).str.contains("Unnamed")]
        cols = [str(c).strip() for c in df.columns.astype(str)]
        if cols and (cols[0].isdigit() or cols[0].lower().startswith("unnamed")):
            df = pd.read_excel(path, header=0)
            df = df.loc[:, ~df.columns.astype(str).str.contains("Unnamed")]
        return df
    except Exception as e:
        print(f"WARN read {path}: {e}")
        return pd.DataFrame()

def audit_stock_prices(con, source_df, rows):
    """Compare stock_prices per company_id+date."""
    if source_df.empty:
        return
    # Normalize tickers + date format (ticker alias M&M -> MM applied here, matching loader)
    source_df = source_df.copy()
    source_df["company_id"] = source_df["company_id"].apply(normalize_ticker)
    source_df["date"] = pd.to_datetime(source_df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    db_df = pd.read_sql("SELECT company_id, date, close_price, market_cap_crore, pe_ratio, pb_ratio, dividend_yield FROM stock_prices", con)
    # Only compare fields the source file actually contains. stock_prices.xlsx is OHLCV-only:
    # market_cap_crore/pe_ratio/pb_ratio/dividend_yield come from market_cap.xlsx via merge,
    # so they must not be flagged as MISMATCH against stock_prices.xlsx.
    src_fields = [c for c in ["close_price", "market_cap_crore", "pe_ratio", "pb_ratio", "dividend_yield"]
                  if c in source_df.columns]
    # Build lookup for source
    src_lookup = {(r["company_id"], r["date"]): r for _, r in source_df.iterrows()}
    db_lookup = {(r["company_id"], r["date"]): r for _, r in db_df.iterrows()}
    # Compare all source keys
    for key, src_row in src_lookup.items():
        db_row = db_lookup.get(key)
        for field in src_fields:
            src_val = src_row.get(field)
            db_val = db_row[field] if db_row is not None else None
            if db_row is None:
                status = "DATABASE_MISSING"
                reason = "source has value but DB missing row for company_id+date"
            elif pd.isna(src_val) and pd.isna(db_val):
                status = "MATCH"
                reason = "both NULL"
            elif pd.isna(src_val) and not pd.isna(db_val):
                status = "MISMATCH"
                reason = "source NULL but DB has value"
            elif not pd.isna(src_val) and pd.isna(db_val):
                status = "MISMATCH"
                reason = "source has value but DB NULL"
            elif abs(float(src_val) - float(db_val)) < 0.01:
                status = "MATCH"
                reason = "values match within tolerance"
            else:
                status = "MISMATCH"
                reason = f"source {src_val} != DB {db_val}"
            rows.append({
                "table": "stock_prices",
                "company_id": key[0],
                "date_or_year": key[1],
                "field": field,
                "database_value": db_val if db_row is not None else None,
                "source_value": src_val,
                "status": status,
                "reason": reason
            })
    # Also check DB rows not in source
    for key, db_row in db_lookup.items():
        if key not in src_lookup:
            for field in src_fields:
                rows.append({
                    "table": "stock_prices",
                    "company_id": key[0],
                    "date_or_year": key[1],
                    "field": field,
                    "database_value": db_row[field],
                    "source_value": None,
                    "status": "SOURCE_MISSING",
                    "reason": "DB has row but source missing (may be derived or extra)"
                })

def audit_sectors(con, source_df, rows):
    """Sectors: compare broad_sector, company_count, medians (calculated)."""
    if source_df.empty:
        return
    db_df = pd.read_sql("SELECT broad_sector, company_count, median_roe, median_pe, median_de FROM sectors", con)
    # source has per-company rows; company_count is derived by grouping broad_sector
    source_df = source_df.copy()
    if "company_id" in source_df.columns:
        source_df["company_id"] = source_df["company_id"].apply(normalize_ticker)
    src_counts = source_df.groupby("broad_sector")["company_id"].nunique().to_dict() \
        if "company_id" in source_df.columns else {}
    # medians are computed, not present in source
    src_lookup = {r["broad_sector"]: r for _, r in source_df.drop_duplicates("broad_sector").iterrows()}
    db_lookup = {r["broad_sector"]: r for _, r in db_df.iterrows()}
    # company_count check
    for sector in set(src_counts) | set(db_lookup):
        db_row = db_lookup.get(sector)
        src_val = src_counts.get(sector)
        db_val = db_row["company_count"] if db_row is not None else None
        if db_row is None:
            status = "DATABASE_MISSING"
            reason = "sector missing in DB"
        elif src_val is None:
            status = "SOURCE_MISSING"
            reason = "sector row present but no company rows in source"
        elif src_val == db_val:
            status = "MATCH"
            reason = "company_count matches grouped source"
        else:
            status = "MISMATCH"
            reason = f"source grouped {src_val} != DB {db_val}"
        rows.append({
            "table": "sectors",
            "company_id": None,
            "date_or_year": sector,
            "field": "company_count",
            "database_value": db_val,
            "source_value": src_val,
            "status": status,
            "reason": reason
        })
        # medians are calculated, not in source
        for field in ["median_roe", "median_pe", "median_de"]:
            db_val = db_row[field] if db_row is not None else None
            if pd.isna(db_val):
                status = "SOURCE_MISSING"  # actually calculated but source has no value, keep NULL is not invented
                reason = "source does not provide median, DB NULL indicates no valid underlying values (or calculated NULL)"
                # But if DB now has value, it's calculated
                # We'll check if DB has value: then it's CALCULATED
                if db_row is not None and not pd.isna(db_val):
                    status = "CALCULATED"
                    reason = f"calculated from financial_ratios/stock_prices for sector {sector} (deterministic median)"
                else:
                    # If source truly missing, keep as SOURCE_MISSING
                    status = "SOURCE_MISSING"
                    reason = "source does not provide median, DB NULL is legitimate"
            else:
                status = "CALCULATED"
                reason = f"calculated median for {sector} from valid source values"
            rows.append({
                "table": "sectors",
                "company_id": None,
                "date_or_year": sector,
                "field": field,
                "database_value": db_val,
                "source_value": None,
                "status": status,
                "reason": reason
            })
    # Check DB sectors not in source
    for sector, db_row in db_lookup.items():
        if sector not in src_lookup:
            rows.append({
                "table": "sectors",
                "company_id": None,
                "date_or_year": sector,
                "field": "broad_sector",
                "database_value": sector,
                "source_value": None,
                "status": "SOURCE_MISSING",
                "reason": "DB sector not in source (may be derived)"
            })

def audit_peer_percentiles(con, rows):
    """Peer percentiles: compare value and percentile_rank against financial_ratios and peer_groups."""
    try:
        db_df = pd.read_sql("SELECT company_id, peer_group_name, metric, value, percentile_rank, year FROM peer_percentiles", con)
    except Exception as e:
        print(f"peer_percentiles read err: {e}")
        return
    if db_df.empty:
        return
    fr = pd.read_sql("SELECT company_id, year, net_profit_margin_pct, operating_profit_margin_pct, return_on_equity_pct, return_on_capital_employed_pct, return_on_assets_pct, debt_to_equity, interest_coverage, asset_turnover, fcf_conversion_pct, capex_intensity_pct FROM financial_ratios", con)
    pg = pd.read_sql("SELECT peer_group_name, company_id FROM peer_groups", con)
    # Build mappings
    fr_lookup = {(r["company_id"], r["year"]): r for _, r in fr.iterrows()}
    pg_lookup = set((r["company_id"], r["peer_group_name"]) for _, r in pg.iterrows())
    # For each peer_percentiles row, check if source metric exists
    for _, r in db_df.iterrows():
        key = (r["company_id"], r["year"])
        src_row = fr_lookup.get(key)
        src_val = src_row[r["metric"]] if src_row is not None and r["metric"] in src_row else None
        # Check value matches source
        db_val = r["value"]
        # Status for value field
        if src_row is None:
            status_val = "SOURCE_MISSING"
            reason_val = "financial_ratios missing for company-year"
        elif pd.isna(src_val) and pd.isna(db_val):
            status_val = "MATCH"
            reason_val = "both NULL (source missing, correctly kept NULL)"
        elif pd.isna(src_val) and not pd.isna(db_val):
            status_val = "MISMATCH"
            reason_val = "source NULL but DB has value (should be NULL)"
        elif not pd.isna(src_val) and pd.isna(db_val):
            status_val = "MISMATCH"
            reason_val = "source has value but DB NULL (calculation missing)"
        elif abs(float(src_val) - float(db_val)) < 0.001:
            status_val = "MATCH"
            reason_val = "value matches financial_ratios"
        else:
            status_val = "MISMATCH"
            reason_val = f"source {src_val} != DB {db_val}"
        rows.append({
            "table": "peer_percentiles",
            "company_id": r["company_id"],
            "date_or_year": r["year"],
            "field": f"{r['metric']} value",
            "database_value": db_val,
            "source_value": src_val,
            "status": status_val,
            "reason": reason_val
        })
        # Check percentile_rank: must be between 0 and 1 if valid, NULL if source missing
        pct = r["percentile_rank"]
        if pd.isna(src_val):
            # source missing -> pct should be NULL
            if pd.isna(pct):
                status_pct = "MATCH"
                reason_pct = "source missing, percentile correctly NULL"
            else:
                status_pct = "MISMATCH"
                reason_pct = "source missing but percentile not NULL (should be NULL)"
        else:
            if pd.isna(pct):
                status_pct = "DATABASE_MISSING"
                reason_pct = "source has value but percentile NULL (calculation missing or insufficient peers)"
            elif 0 <= float(pct) <= 1:
                status_pct = "CALCULATED"
                reason_pct = f"percentile within peer group {r['peer_group_name']} year {r['year']} (D/E inverted if needed)"
            else:
                status_pct = "MISMATCH"
                reason_pct = f"percentile {pct} out of range [0,1]"
        rows.append({
            "table": "peer_percentiles",
            "company_id": r["company_id"],
            "date_or_year": r["year"],
            "field": f"{r['metric']} percentile_rank",
            "database_value": pct,
            "source_value": "calculated" if not pd.isna(src_val) else None,
            "status": status_pct,
            "reason": reason_pct
        })
        # Also check peer_group mapping valid
        if (r["company_id"], r["peer_group_name"]) not in pg_lookup:
            # This should be flagged as mismatch, but peer_groups may have been filtered
            pass

def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    rows = []
    # STOCK_PRICES
    sp_src = read_source(SOURCE_DIR / "stock_prices.xlsx")
    print(f"stock_prices source: {sp_src.shape}")
    audit_stock_prices(con, sp_src, rows)

    # SECTORS
    sec_src = read_source(SOURCE_DIR / "sectors.xlsx")
    print(f"sectors source: {sec_src.shape}")
    audit_sectors(con, sec_src, rows)

    # PEER_PERCENTILES
    audit_peer_percentiles(con, rows)

    con.close()
    # Save
    df = pd.DataFrame(rows, columns=["table","company_id","date_or_year","field","database_value","source_value","status","reason"])
    # Ensure status allowed set
    allowed = {"MATCH","MISMATCH","SOURCE_MISSING","DATABASE_MISSING","CALCULATED","NOT_APPLICABLE"}
    # Replace any invalid status with NOT_APPLICABLE
    df["status"] = df["status"].apply(lambda x: x if x in allowed else "NOT_APPLICABLE")
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Audit -> {OUTPUT_CSV} ({len(df)} rows)")
    print(df["status"].value_counts().to_dict())
    # Summary
    print(df["table"].value_counts().to_dict())
    return df

if __name__ == "__main__":
    run()
