"""Peer percentiles: PERCENT_RANK within peer groups, invert D/E. Canonical long format."""
import pathlib
import sqlite3
import pandas as pd
import numpy as np

DB_PATH = pathlib.Path("data/nifty100.db")

METRICS = [
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "return_on_assets_pct",
    "debt_to_equity",
    "interest_coverage",
    "asset_turnover",
    "fcf_conversion_pct",
    "capex_intensity_pct",
]

def percent_rank(series):
    """PERCENT_RANK: (rank-1)/(n-1) within group, 0..1 . Only valid non-null values considered."""
    n = series.notna().sum()
    if n <= 1:
        return pd.Series([np.nan if pd.isna(v) else 0.5 for v in series], index=series.index)
    r = series.rank(method="min", pct=False)
    return (r - 1) / (n - 1)

def compute_peer_percentiles(db_path=DB_PATH):
    con = sqlite3.connect(str(db_path))
    pg = pd.read_sql("SELECT * FROM peer_groups", con)
    fr = pd.read_sql("SELECT * FROM financial_ratios", con)

    if pg.empty or fr.empty:
        print("No peer groups or financial ratios, skipping peer percentiles")
        con.close()
        return pd.DataFrame()

    # Build mapping: one company may appear in multiple groups - keep first, but for long format we need to generate one row per company/group/metrics/year.
    # For determinism, if company belongs to multiple groups, we generate percentiles for each group separately.
    # However spec says company_id + peer_group_name + metric + year PK, so multiple groups per company allowed.

    # Ensure peer_percentiles table exists with canonical schema (long format)
    cur = con.cursor()
    cur.execute("DROP TABLE IF EXISTS peer_percentiles")
    cur.execute("""
        CREATE TABLE peer_percentiles (
            company_id TEXT NOT NULL,
            peer_group_name TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL,
            percentile_rank REAL,
            year TEXT NOT NULL,
            PRIMARY KEY (company_id, peer_group_name, metric, year),
            FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
        )
    """)

    # Group financial ratios by peer_group and year
    # First, map each company to its peer groups (list)
    group_members = pg.groupby("peer_group_name")["company_id"].apply(list).to_dict()
    # Also map company to groups for quick lookup (for diagnostic)
    company_groups = {}
    for grp, members in group_members.items():
        for cid in members:
            company_groups.setdefault(cid, []).append(grp)

    # Prepare long format rows
    rows = []
    diagnostics = []
    # For each peer group and year, compute percentiles per metric
    # Need to get distinct years from financial_ratios
    years = fr["year"].dropna().unique()
    for pg_name, member_cids in group_members.items():
        for year in years:
            group_fr = fr[(fr["company_id"].isin(member_cids)) & (fr["year"] == year)]
            if group_fr.empty:
                continue
            for metric in METRICS:
                if metric not in group_fr.columns:
                    continue
                # Extract valid values only
                # For D/E, invert: lower is better, so calculate percentile on negated values
                s_raw = group_fr[metric]
                # Keep track of valid vs missing
                # Compute percentile only for valid values
                if metric == "debt_to_equity":
                    s_trans = -s_raw  # invert
                else:
                    s_trans = s_raw
                pct_series = percent_rank(s_trans)
                # Now for each member in this group-year, create row
                for idx, r in group_fr.iterrows():
                    cid = r["company_id"]
                    val = r[metric]
                    pct = pct_series.loc[idx]
                    # If source value is missing, percentile must be NULL and reason SOURCE_MISSING
                    if pd.isna(val):
                        pct = np.nan
                        status = "SOURCE_MISSING"
                        reason = f"financial_ratios.{metric} is NULL for {cid} {year}"
                    elif pd.isna(pct):
                        # percentile calculation missing due to insufficient peers
                        status = "CALCULATION_MISSING"
                        reason = f"n_valid <=1 in peer group {pg_name} year {year} for metric {metric}"
                    else:
                        status = "VALID"
                        reason = "calculated"
                    # For diagnostic, we will collect later; for DB, only valid pct or NULL
                    # Value stored is source metric value, percentile_rank is pct
                    rows.append({
                        "company_id": cid,
                        "peer_group_name": pg_name,
                        "metric": metric,
                        "value": float(val) if pd.notna(val) else None,
                        "percentile_rank": float(pct) if pd.notna(pct) else None,
                        "year": year
                    })
                    diagnostics.append({
                        "company_id": cid,
                        "year": year,
                        "peer_group_name": pg_name,
                        "metric": metric,
                        "source_value": float(val) if pd.notna(val) else None,
                        "percentile_rank": float(pct) if pd.notna(pct) else None,
                        "status": status,
                        "reason": reason
                    })
        # Also handle members with no valid group? Already covered

    # Also need to handle companies with no peer group mapping -> they will have no rows, which is correct per MAPPING_MISSING
    # For completeness, add diagnostic for companies-year with no peer group
    all_cids_years = fr[["company_id","year"]].drop_duplicates()
    covered = set((d["company_id"], d["year"]) for d in diagnostics)
    for _, r in all_cids_years.iterrows():
        cid = r["company_id"]
        year = r["year"]
        if (cid, year) not in set((x["company_id"], x["year"]) for x in diagnostics if x["company_id"]==cid and x["year"]==year):
            # Check if company has no peer group at all
            if cid not in company_groups:
                for metric in METRICS:
                    val = fr[(fr["company_id"]==cid) & (fr["year"]==year)][metric].values
                    val = val[0] if len(val)>0 else None
                    diagnostics.append({
                        "company_id": cid,
                        "year": year,
                        "peer_group_name": None,
                        "metric": metric,
                        "source_value": float(val) if pd.notna(val) else None,
                        "percentile_rank": None,
                        "status": "MAPPING_MISSING",
                        "reason": f"company {cid} has no peer_group mapping"
                    })

    # Insert into DB
    if rows:
        df = pd.DataFrame(rows)
        # Remove duplicates on PK keep last
        df = df.drop_duplicates(subset=["company_id","peer_group_name","metric","year"], keep="last")
        df.to_sql("peer_percentiles", con, if_exists="append", index=False)
        con.commit()
        print(f"Inserted {len(df)} peer_percentile rows (long format)")
    else:
        df = pd.DataFrame(rows)
        print("No peer percentile rows to insert")

    # Generate diagnostic report
    diag_df = pd.DataFrame(diagnostics)
    # Save diagnostic
    out_path = pathlib.Path("output/peer_percentiles_diagnostic.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not diag_df.empty:
        # Ensure columns order
        diag_cols = ["company_id","year","peer_group_name","metric","source_value","percentile_rank","status","reason"]
        for c in diag_cols:
            if c not in diag_df.columns:
                diag_df[c] = None
        diag_df = diag_df[diag_cols]
        diag_df.to_csv(out_path, index=False)
        print(f"Diagnostic report -> {out_path} ({len(diag_df)} rows)")
        # Summary
        print(diag_df["status"].value_counts().to_dict())
    con.close()
    return df if 'df' in locals() else pd.DataFrame()

if __name__ == "__main__":
    df = compute_peer_percentiles()
    print(f"Peer percentiles: {len(df)} rows")
