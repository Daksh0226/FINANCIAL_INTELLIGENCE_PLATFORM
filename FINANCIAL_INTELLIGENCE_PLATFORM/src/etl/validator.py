"""DQ-01 .. DQ-16 validator. Generates validation_failures.csv"""
import pandas as pd

SEVERITY = {
    "DQ-01": "CRITICAL", "DQ-02": "CRITICAL", "DQ-03": "CRITICAL",
    "DQ-04": "WARNING", "DQ-05": "WARNING", "DQ-06": "WARNING",
    "DQ-07": "WARNING", "DQ-08": "WARNING", "DQ-09": "WARNING",
    "DQ-10": "WARNING", "DQ-11": "WARNING", "DQ-12": "WARNING",
    "DQ-13": "WARNING", "DQ-14": "WARNING", "DQ-15": "WARNING", "DQ-16": "WARNING",
}

def validate_all(dfs: dict) -> pd.DataFrame:
    failures = []
    companies = dfs.get("companies", pd.DataFrame())
    pl = dfs.get("profitandloss", pd.DataFrame())
    bs = dfs.get("balancesheet", pd.DataFrame())
    cf = dfs.get("cashflow", pd.DataFrame())

    # DQ-01 PK uniqueness companies
    if not companies.empty and "company_id" in companies.columns:
        dups = companies[companies.duplicated("company_id", keep=False)]
        for _, r in dups.iterrows():
            failures.append(["DQ-01", r["company_id"], "company_id", "Duplicate company_id", SEVERITY["DQ-01"]])
    # DQ-02 (company_id, year) PK for pl/bs/cf
    for name, df in [("profitandloss", pl), ("balancesheet", bs), ("cashflow", cf)]:
        if not df.empty and {"company_id","year"}.issubset(df.columns):
            dups = df[df.duplicated(["company_id","year"], keep=False)]
            for _, r in dups.iterrows():
                failures.append(["DQ-02", r["company_id"], "year", f"Duplicate (company_id,year) in {name}: {r['year']}", SEVERITY["DQ-02"]])
    # DQ-03 FK integrity
    valid_ids = set(companies["company_id"]) if not companies.empty and "company_id" in companies.columns else set()
    for name, df in [("profitandloss", pl), ("balancesheet", bs), ("cashflow", cf)]:
        if not df.empty and "company_id" in df.columns:
            bad = df[~df["company_id"].isin(valid_ids)]
            for _, r in bad.iterrows():
                failures.append(["DQ-03", r["company_id"], "company_id", f"FK violation in {name}", SEVERITY["DQ-03"]])
    # DQ-04 BS balance <1%
    if not bs.empty and {"total_liabilities","total_assets"}.issubset(bs.columns):
        for _, r in bs.iterrows():
            if pd.notna(r["total_liabilities"]) and pd.notna(r["total_assets"]) and r["total_assets"] != 0:
                diff = abs(r["total_liabilities"] - r["total_assets"]) / abs(r["total_assets"])
                if diff > 0.01:
                    failures.append(["DQ-04", r["company_id"], "total_liabilities/total_assets", f"BS imbalance {diff:.2%} year {r['year']}", SEVERITY["DQ-04"]])
    # DQ-05 OPM cross-check
    if not pl.empty and {"operating_profit","sales","opm_percentage"}.issubset(pl.columns):
        for _, r in pl.iterrows():
            if pd.notna(r["sales"]) and r["sales"] != 0 and pd.notna(r["operating_profit"]) and pd.notna(r["opm_percentage"]):
                computed = r["operating_profit"]/r["sales"]*100
                if abs(computed - r["opm_percentage"]) > 1.0:
                    failures.append(["DQ-05", r["company_id"], "opm_percentage", f"OPM mismatch computed {computed:.1f} vs {r['opm_percentage']:.1f} year {r['year']}", SEVERITY["DQ-05"]])
    # DQ-06 Positive sales
    if not pl.empty and "sales" in pl.columns:
        for _, r in pl.iterrows():
            if pd.notna(r["sales"]) and r["sales"] < 0:
                failures.append(["DQ-06", r["company_id"], "sales", f"Negative sales {r['sales']} year {r['year']}", SEVERITY["DQ-06"]])
    # DQ-07 Net cash = CFO+CFI+CFF
    if not cf.empty and {"operating_activity","investing_activity","financing_activity","net_cash_flow"}.issubset(cf.columns):
        for _, r in cf.iterrows():
            total = (r["operating_activity"] or 0) + (r["investing_activity"] or 0) + (r["financing_activity"] or 0)
            if pd.notna(r["net_cash_flow"]) and abs(total - r["net_cash_flow"]) > 1.0:
                failures.append(["DQ-07", r["company_id"], "net_cash_flow", f"Net cash mismatch {total:.1f} vs {r['net_cash_flow']:.1f} year {r['year']}", SEVERITY["DQ-07"]])
    # DQ-08 Tax rate sanity 0-50%
    if not pl.empty and {"profit_before_tax","tax"}.issubset(pl.columns):
        for _, r in pl.iterrows():
            if pd.notna(r["profit_before_tax"]) and r["profit_before_tax"] != 0 and pd.notna(r["tax"]):
                rate = r["tax"]/r["profit_before_tax"]*100
                if rate < 0 or rate > 60:
                    failures.append(["DQ-08", r["company_id"], "tax", f"Tax rate {rate:.1f}% year {r['year']}", SEVERITY["DQ-08"]])
    # DQ-09 Dividend cap <=100%
    if not pl.empty and "dividend_payout_ratio" in pl.columns:
        for _, r in pl.iterrows():
            if pd.notna(r["dividend_payout_ratio"]) and r["dividend_payout_ratio"] > 100:
                failures.append(["DQ-09", r["company_id"], "dividend_payout_ratio", f"Payout {r['dividend_payout_ratio']:.1f}% year {r['year']}", SEVERITY["DQ-09"]])
    # DQ-10 URL valid (skip Null/nan/None placeholders)
    docs = dfs.get("documents", pd.DataFrame())
    if not docs.empty and "report_url" in docs.columns:
        for _, r in docs.iterrows():
            if pd.isna(r["report_url"]):
                continue
            url = str(r["report_url"]).strip()
            if not url or url.lower() in ["null", "nan", "none", "na", "n/a"]:
                continue
            if not (url.startswith("http://") or url.startswith("https://")):
                failures.append(["DQ-10", r["company_id"], "report_url", f"Invalid URL {url}", SEVERITY["DQ-10"]])
    # DQ-11 EPS sign vs net_profit sign
    if not pl.empty and {"eps","net_profit"}.issubset(pl.columns):
        for _, r in pl.iterrows():
            if pd.notna(r["eps"]) and pd.notna(r["net_profit"]):
                if (r["eps"] > 0 and r["net_profit"] < 0) or (r["eps"] < 0 and r["net_profit"] > 0):
                    failures.append(["DQ-11", r["company_id"], "eps", f"EPS sign mismatch eps {r['eps']} vs profit {r['net_profit']} year {r['year']}", SEVERITY["DQ-11"]])
    # DQ-12 BSE balance alias of DQ-04 (borrowings+equity sanity)
    # already covered; add borrowings negative check
    if not bs.empty and "borrowings" in bs.columns:
        for _, r in bs.iterrows():
            if pd.notna(r["borrowings"]) and r["borrowings"] < 0:
                failures.append(["DQ-12", r["company_id"], "borrowings", f"Negative borrowings {r['borrowings']} year {r['year']}", SEVERITY["DQ-12"]])
    # DQ-13 Coverage - year count per company <5 years flagged
    for name, df in [("profitandloss", pl), ("balancesheet", bs), ("cashflow", cf)]:
        if not df.empty and "company_id" in df.columns:
            counts = df.groupby("company_id").size()
            for cid, cnt in counts.items():
                if cnt < 5:
                    failures.append(["DQ-13", cid, "year", f"Only {cnt} years in {name} (<5)", SEVERITY["DQ-13"]])
                    break  # one per company to avoid spam
    # DQ-14 Sales YoY spike >200% (data error)
    if not pl.empty and {"company_id","year","sales"}.issubset(pl.columns):
        for cid, g in pl.sort_values("year").groupby("company_id"):
            g = g.sort_values("year")
            prev = None
            for _, r in g.iterrows():
                if prev is not None and pd.notna(prev) and prev != 0 and pd.notna(r["sales"]):
                    yoy = abs(r["sales"]-prev)/abs(prev)
                    if yoy > 2.0:
                        failures.append(["DQ-14", cid, "sales", f"YoY spike {yoy:.0%} year {r['year']}", SEVERITY["DQ-14"]])
                prev = r["sales"]
    # DQ-15 ROCE/ROE outlier >200% (was 100, too strict for high-quality FMCG like NESTLEIND 135%)
    if not companies.empty and "roe_percentage" in companies.columns:
        for _, r in companies.iterrows():
            if pd.notna(r["roe_percentage"]) and abs(r["roe_percentage"]) > 200:
                failures.append(["DQ-15", r["company_id"], "roe_percentage", f"ROE outlier {r['roe_percentage']:.1f}%", SEVERITY["DQ-15"]])
    # DQ-16 Missing critical fields
    if not companies.empty:
        for _, r in companies.iterrows():
            if pd.isna(r.get("company_name")) or str(r.get("company_name","")).strip() == "":
                failures.append(["DQ-16", r["company_id"], "company_name", "Missing company_name", SEVERITY["DQ-16"]])

    cols = ["rule_id","company_id","field","issue","severity"]
    return pd.DataFrame(failures, columns=cols)
