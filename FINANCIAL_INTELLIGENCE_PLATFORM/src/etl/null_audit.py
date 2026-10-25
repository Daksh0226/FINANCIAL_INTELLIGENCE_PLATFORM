"""Null value audit: generates output/null_value_audit.csv"""
import pathlib
import sqlite3
import pandas as pd

DB_PATH = pathlib.Path("data/nifty100.db")
SOURCE_DIR = pathlib.Path("data/source")
OUTPUT_CSV = pathlib.Path("output/null_value_audit.csv")

def read_source_nulls(path: pathlib.Path, col: str):
    """Check if source file contains non-null values for col (header=1)."""
    if not path.exists():
        return None  # unknown
    try:
        df = pd.read_excel(path, header=1)
        df = df.loc[:, ~df.columns.astype(str).str.contains("Unnamed")]
        if col not in df.columns:
            # Try case-insensitive
            lower = {c.lower(): c for c in df.columns}
            if col.lower() in lower:
                col = lower[col.lower()]
            else:
                return False
        # Check if source has any non-null valid values
        series = df[col]
        has_value = series.notna().sum() > 0 and (series.dropna().astype(str).str.strip() != "").sum() > 0
        return has_value
    except Exception as e:
        print(f"WARN source null check {path} {col}: {e}")
        return None

def generate():
    pathlib.Path("output").mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    # Get all tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [r[0] for r in cur.fetchall()]
    rows = []
    # Map table to source file for null source check
    table_source_map = {
        "companies": SOURCE_DIR / "companies.xlsx",
        "sectors": SOURCE_DIR / "sectors.xlsx",
        "stock_prices": SOURCE_DIR / "stock_prices.xlsx",
        "peer_groups": SOURCE_DIR / "peer_groups.xlsx",
        "financial_ratios": SOURCE_DIR / "balancesheet.xlsx",  # derived, so source not direct
        "profitandloss": SOURCE_DIR / "profitandloss.xlsx",
        "balancesheet": SOURCE_DIR / "balancesheet.xlsx",
        "cashflow": SOURCE_DIR / "cashflow.xlsx",
        "analysis": SOURCE_DIR / "analysis.xlsx",
        "documents": SOURCE_DIR / "documents.xlsx",
        "prosandcons": SOURCE_DIR / "prosandcons.xlsx",
        "peer_percentiles": None,  # calculated
    }
    for table in tables:
        if table == "peer_percentiles":
            # Handled specially
            pass
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        total = cur.fetchone()[0]
        cur.execute(f"PRAGMA table_info({table})")
        cols = cur.fetchall()  # cid, name, type, notnull, dflt, pk
        for col_info in cols:
            col = col_info[1]
            cur.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" IS NULL')
            null_count = cur.fetchone()[0]
            null_pct = round(null_count / total * 100, 2) if total > 0 else 0
            # Determine source_contains_value and recommended_action
            source_path = table_source_map.get(table)
            source_contains = None
            if source_path is None:
                # For peer_percentiles and derived
                if table == "peer_percentiles":
                    source_contains = True  # underlying financial_ratios has values
                elif table == "financial_ratios":
                    source_contains = True  # computed from PL/BS/CF
                else:
                    source_contains = None
            else:
                # For sectors median columns, source does NOT contain value (calculated)
                if table == "sectors" and col in ["median_roe","median_pe","median_de"]:
                    source_contains = False
                elif table == "stock_prices" and col in ["close_price","market_cap_crore","pe_ratio","pb_ratio","dividend_yield"]:
                    source_contains = read_source_nulls(source_path, col)
                else:
                    source_contains = read_source_nulls(source_path, col)
            # Determine recommended action and reason
            if null_count == 0:
                recommended = "NO_ACTION"
                reason = "no nulls"
            elif table == "sectors" and col in ["median_roe","median_pe","median_de"]:
                if null_count == 0:
                    recommended = "NO_ACTION"
                    reason = "calculated median present"
                else:
                    # Some nulls may be legitimate if sector has no valid underlying values
                    recommended = "INVESTIGATE"
                    reason = "median is calculated; NULL indicates no valid underlying values for that sector/year (SOURCE_MISSING legitimate)"
            elif table == "stock_prices":
                if null_count == 0:
                    recommended = "NO_ACTION"
                    reason = "all values present from canonical source"
                else:
                    if source_contains:
                        recommended = "FIX_ETL"
                        reason = "source has value but DB NULL - ETL failed to load"
                    else:
                        recommended = "KEEP_NULL"
                        reason = "source also NULL, genuinely missing"
            elif table == "peer_percentiles":
                if col in ["value","percentile_rank"]:
                    if source_contains:
                        # Need to check if null is due to source missing or calculation missing
                        # For now, if null_count >0, some are source_missing (legitimate)
                        recommended = "KEEP_NULL"
                        reason = "NULL is legitimate when source metric is missing or peer group insufficient; check peer_percentiles_diagnostic.csv for status SOURCE_MISSING/MAPPING_MISSING"
                    else:
                        recommended = "KEEP_NULL"
                        reason = "source missing, NULL legitimate"
                else:
                    recommended = "KEEP_NULL"
                    reason = "peer group mapping missing legitimate"
            elif table == "financial_ratios":
                # Many ratios may be genuinely NULL due to missing PL/BS/CF inputs
                recommended = "KEEP_NULL"
                reason = "financial_ratios NULL when underlying PL/BS/CF missing or formula yields None (e.g., interest 0 -> ICR NULL)"
            else:
                if source_contains is False:
                    recommended = "KEEP_NULL"
                    reason = "source has no value for this field (genuinely missing)"
                elif source_contains is True:
                    recommended = "FIX_ETL"
                    reason = "source has value but DB NULL - ETL bug or schema mismatch"
                else:
                    recommended = "INVESTIGATE"
                    reason = "could not determine source status; manual check needed"
            rows.append({
                "table": table,
                "column": col,
                "total_rows": total,
                "null_count": null_count,
                "null_percentage": null_pct,
                "source_contains_value": source_contains,
                "recommended_action": recommended,
                "reason": reason
            })
    df = pd.DataFrame(rows, columns=["table","column","total_rows","null_count","null_percentage","source_contains_value","recommended_action","reason"])
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Null audit -> {OUTPUT_CSV} ({len(df)} rows)")
    print(df[df["null_count"]>0][["table","column","null_count","null_percentage","recommended_action"]].to_string())
    # Also print summary
    print("\nSummary by recommended_action:")
    print(df["recommended_action"].value_counts().to_dict())
    con.close()
    return df

if __name__ == "__main__":
    generate()
