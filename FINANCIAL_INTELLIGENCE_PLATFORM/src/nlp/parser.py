"""NLP parser: regex (\\d+)\\s*Years?:?\\s*(-?[\\d.]+)% """
import re, pathlib, sqlite3
import pandas as pd

DB_PATH = pathlib.Path("data/nifty100.db")
OUTPUT_DIR = pathlib.Path("output")

# Period label followed by a percentage. The value may be negative (e.g. "3 Years: -1%"),
# so the sign must be part of the pattern or those values get dropped as failures.
PAT = re.compile(r"(\d+)\s*Years?:?\s*(-?[\d.]+)%", re.I)

METRIC_COLS = ["compounded_sales_growth","compounded_profit_growth","stock_price_cagr","roe"]

def parse_value(text):
    if text is None or pd.isna(text):
        return []
    s = str(text)
    return [(int(m.group(1)), float(m.group(2))) for m in PAT.finditer(s)]

def parse_analysis_table(db_path=DB_PATH):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        # analysis holds one row per (company, period), so analysis_id is carried
        # through to the output to keep each parsed value traceable to its source row.
        df = pd.read_sql("SELECT analysis_id, company_id, compounded_sales_growth, compounded_profit_growth, stock_price_cagr, roe FROM analysis", con)
        try:
            fr = pd.read_sql("SELECT company_id, year, revenue_cagr_5yr, pat_cagr_5yr FROM financial_ratios", con)
        except Exception:
            fr = pd.DataFrame()
    finally:
        con.close()
    parsed_rows = []
    failures = []
    for _, r in df.iterrows():
        cid = r["company_id"]
        aid = r["analysis_id"] if "analysis_id" in r.index else None
        for col in METRIC_COLS:
            val = r[col]
            matches = parse_value(val)
            if matches:
                for years, pct in matches:
                    parsed_rows.append({"analysis_id": aid, "company_id": cid, "metric_type": col, "period_years": years, "value_pct": pct, "field": col, "years": years, "raw": val})
            else:
                if pd.notna(val) and str(val).strip() != "":
                    failures.append({"analysis_id": aid, "company_id": cid, "field": col, "raw": val, "reason": "no regex match"})
    parsed_df = pd.DataFrame(parsed_rows)
    fail_df = pd.DataFrame(failures, columns=["analysis_id","company_id","field","raw","reason"])
    # ensure spec columns exist
    if not parsed_df.empty:
        # keep both naming conventions for compatibility
        if "metric_type" not in parsed_df.columns:
            parsed_df["metric_type"] = parsed_df["field"]
        if "period_years" not in parsed_df.columns:
            parsed_df["period_years"] = parsed_df["years"]
    parsed_df.to_csv(OUTPUT_DIR / "analysis_parsed.csv", index=False)
    fail_df.to_csv(OUTPUT_DIR / "parse_failures.csv", index=False)
    # cross-validate vs computed CAGR (log divergence >5%)
    try:
        if not parsed_df.empty and not fr.empty:
            # latest per company
            fr["year_int"] = pd.to_numeric(fr["year"], errors="coerce")
            latest = fr.sort_values("year_int").groupby("company_id").tail(1)
            # compare where parsed has 10-year sales growth vs revenue_cagr_5yr etc (approx) - log if >5%
            with open(OUTPUT_DIR / "parse_validation.log", "w") as vf:
                for _, pr in parsed_df.iterrows():
                    # map field to computed column
                    cmap = {"compounded_sales_growth":"revenue_cagr_5yr", "compounded_profit_growth":"pat_cagr_5yr"}
                    col = cmap.get(pr["field"])
                    if col and pr["period_years"]==10:
                        row = latest[latest["company_id"]==pr["company_id"]]
                        if not row.empty:
                            comp_val = row.iloc[0][col]
                            if pd.notna(comp_val) and abs(comp_val - pr["value_pct"]) > 5:
                                vf.write(f"{pr['company_id']} {pr['field']} parsed {pr['value_pct']} vs computed {comp_val:.1f} diff >5%\n")
        else:
            (OUTPUT_DIR / "parse_validation.log").write_text("")
    except Exception:
        pass
    return parsed_df, fail_df

if __name__ == "__main__":
    p,f = parse_analysis_table()
    print(f"Parsed {len(p)} rows, failures {len(f)}")
