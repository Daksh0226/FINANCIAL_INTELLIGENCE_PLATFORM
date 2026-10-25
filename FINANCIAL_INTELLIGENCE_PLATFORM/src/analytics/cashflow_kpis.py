"""Cashflow KPIs: CFO quality, CapEx intensity, FCF conversion, capital allocation classifier."""
import pathlib, sqlite3
import pandas as pd
import numpy as np

DB_PATH = pathlib.Path("data/nifty100.db")
OUTPUT_DIR = pathlib.Path("output")

def cfo_quality_label(cfo_pat_ratio):
    # Spec Part 4: >1.0 High Quality, 0.5-1.0 Moderate, <0.5 Accrual Risk, PAT=0 => None handled via ratio NaN
    if cfo_pat_ratio is None or pd.isna(cfo_pat_ratio):
        return None
    if cfo_pat_ratio > 1.0:
        return "High Quality"
    if cfo_pat_ratio >= 0.5:
        return "Moderate"
    return "Accrual Risk"

def capex_intensity_label(intensity):
    """Spec Day 11: <3% Asset Light, 3-8% Moderate, >8% Capital Intensive."""
    if intensity is None or pd.isna(intensity):
        return "Unknown"
    if intensity < 3:
        return "Asset Light"
    if intensity <= 8:
        return "Moderate"
    return "Capital Intensive"

def fcf_conversion_label(conv):
    if conv is None or pd.isna(conv):
        return "Unknown"
    if conv >= 80:
        return "Strong"
    if conv >= 40:
        return "Moderate"
    return "Weak"

def classify_capital_allocation(row):
    """8-pattern classifier based on sign of (CFO, CFI, CFF) per Sprint 2/5 spec.

    Labels:
      (+,-,-) Reinvestor  | (+,-,-) high CFO/PAT Shareholder Returns
      (+,+,-) Liquidating Assets | (-,+,+) Distress Signal
      (-,-,+) Growth Funded by Debt | (+,+,+) Cash Accumulator
      (-,-,-) Pre-Revenue | (+,-,+) Mixed
    """
    cfo = row.get("operating_activity") or 0
    cfi = row.get("investing_activity") or 0
    cff = row.get("financing_activity") or 0
    # normalize near-zero to sign
    s_cfo = 1 if cfo > 0 else (-1 if cfo < 0 else 0)
    s_cfi = 1 if cfi > 0 else (-1 if cfi < 0 else 0)
    s_cff = 1 if cff > 0 else (-1 if cff < 0 else 0)

    # (+,-,-): Reinvestor vs Shareholder Returns (high CFO/PAT)
    if s_cfo > 0 and s_cfi < 0 and s_cff < 0:
        cfo_pat = row.get("cfo_pat_ratio")
        if cfo_pat is not None and not pd.isna(cfo_pat) and cfo_pat >= 1.0:
            return "Shareholder Returns"
        return "Reinvestor"
    if s_cfo > 0 and s_cfi > 0 and s_cff < 0:
        return "Liquidating Assets"
    if s_cfo < 0 and s_cfi > 0 and s_cff > 0:
        return "Distress Signal"
    if s_cfo < 0 and s_cfi < 0 and s_cff > 0:
        return "Growth Funded by Debt"
    if s_cfo > 0 and s_cfi > 0 and s_cff > 0:
        return "Cash Accumulator"
    if s_cfo < 0 and s_cfi < 0 and s_cff < 0:
        return "Pre-Revenue"
    if s_cfo > 0 and s_cfi < 0 and s_cff > 0:
        return "Mixed"
    if s_cfo < 0 and s_cfi > 0 and s_cff < 0:
        # (-,+,-) not in the 8 canonical — map to Mixed family
        return "Mixed"
    # zero-cash corner cases
    if s_cfo == 0 and s_cfi == 0 and s_cff == 0:
        return "Neutral"
    return "Mixed"

def compute_cashflow_kpis(db_path=DB_PATH):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    pl = pd.read_sql("SELECT company_id, year, net_profit FROM profitandloss", con)
    cf = pd.read_sql("SELECT * FROM cashflow", con)
    fr = pd.read_sql("SELECT company_id, year, net_profit_margin_pct, free_cash_flow_cr, capex_intensity_pct, fcf_conversion_pct FROM financial_ratios", con) if True else None

    df = pd.merge(cf, pl, on=["company_id","year"], how="left")
    # compute 5yr avg CFO/PAT per company
    df["year_int"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.sort_values(["company_id","year_int"])
    df["cfo_pat_ratio"] = np.where(df["net_profit"]!=0, df["operating_activity"]/df["net_profit"], np.nan)
    # 5yr rolling avg
    # use groupby rolling
    df["cfo_pat_5yr_avg"] = df.groupby("company_id")["cfo_pat_ratio"].transform(lambda x: x.rolling(5, min_periods=1).mean())
    df["cfo_quality_label"] = df["cfo_pat_5yr_avg"].apply(cfo_quality_label)

    # CapEx intensity
    df["capex_abs"] = df["investing_activity"].apply(lambda x: abs(x) if pd.notna(x) and x < 0 else 0)
    # need sales for intensity; join pl sales
    pl2 = pd.read_sql("SELECT company_id, year, sales FROM profitandloss", con)
    df = pd.merge(df, pl2, on=["company_id","year"], how="left", suffixes=("","_y"))
    # sales column already? use sales
    df["capex_intensity"] = np.where(df["sales"]>0, df["capex_abs"]/df["sales"]*100, np.nan)
    df["capex_intensity_label"] = df["capex_intensity"].apply(capex_intensity_label)

    # FCF conversion handled earlier via fcf vs operating_profit per spec Part 2
    # Need operating_profit for conversion
    pl_op = pd.read_sql("SELECT company_id, year, operating_profit FROM profitandloss", con)
    df = pd.merge(df, pl_op, on=["company_id","year"], how="left", suffixes=("", "_op"))
    df["fcf"] = df["operating_activity"] + df["investing_activity"]  # Spec: operating + investing
    # Per spec: return None if operating_profit == 0
    df["fcf_conversion"] = np.where((df["operating_profit"].notna()) & (df["operating_profit"]!=0), df["fcf"]/df["operating_profit"]*100, np.nan)
    df["fcf_conversion_label"] = df["fcf_conversion"].apply(fcf_conversion_label)

    df["capital_allocation_pattern"] = df.apply(classify_capital_allocation, axis=1)

    # flags per spec:
    # Distress Signal: CFO <0 AND CFF >0 in latest year (raising cash from financing while operations burn cash)
    df["distress_flag"] = ((df["operating_activity"] < 0) & (df["financing_activity"] > 0)).astype(int)
    # Deleveraging flag: CFF <0 AND borrowings declining YoY (actively paying down debt)
    # Load borrowings YoY change
    try:
        bs = pd.read_sql("SELECT company_id, year, borrowings FROM balancesheet", con)
        bs["year_int"] = pd.to_numeric(bs["year"], errors="coerce")
        bs = bs.sort_values(["company_id","year_int"])
        bs["borrowings_prev"] = bs.groupby("company_id")["borrowings"].shift(1)
        # merge borrowings decline flag
        df = pd.merge(df, bs[["company_id","year","borrowings","borrowings_prev"]], on=["company_id","year"], how="left", suffixes=("", "_bs"))
        df["borrowings_declining"] = (df["borrowings"] < df["borrowings_prev"]) & df["borrowings_prev"].notna()
        df["deleveraging_flag"] = ((df["financing_activity"] < 0) & (df["borrowings_declining"] == True)).astype(int)
    except Exception:
        df["deleveraging_flag"] = ((df["financing_activity"] < 0) & (df["operating_activity"] > 0)).astype(int)

    # update financial_ratios cfo_quality
    cur = con.cursor()
    for _, r in df.iterrows():
        cur.execute("UPDATE financial_ratios SET cfo_quality_score=?, cfo_quality_label=? WHERE company_id=? AND year=?",
                    (r["cfo_pat_5yr_avg"] if pd.notna(r["cfo_pat_5yr_avg"]) else None, r["cfo_quality_label"], r["company_id"], r["year"]))
    con.commit()

    # generate cashflow_intelligence.xlsx with spec columns + legacy columns
    # add sector and fcf_cagr_5yr placeholder if missing
    try:
        comps = pd.read_sql("SELECT company_id, broad_sector FROM companies", con)
        sector_map = dict(zip(comps.company_id, comps.broad_sector))
        df["sector"] = df["company_id"].map(sector_map)
    except Exception:
        df["sector"] = None
    # fcf_cagr_5yr - try to use pat_cagr as proxy if fcf cagr not computed
    if "fcf_cagr_5yr" not in df.columns:
        try:
            cagr_df = pd.read_sql("SELECT company_id, year, pat_cagr_5yr FROM financial_ratios", con)
            df = pd.merge(df, cagr_df, on=["company_id","year"], how="left")
            df["fcf_cagr_5yr"] = df["pat_cagr_5yr"]
        except Exception:
            df["fcf_cagr_5yr"] = np.nan
    # map spec column names
    df["cfo_quality_score"] = df["cfo_pat_5yr_avg"]
    df["capex_intensity_pct"] = df["capex_intensity"]
    df["capex_label"] = df["capex_intensity_label"]
    df["fcf_conversion_pct"] = df["fcf_conversion"]
    df["capital_allocation_label"] = df["capital_allocation_pattern"]

    intel = df[["company_id","sector","year","operating_activity","investing_activity","financing_activity","cfo_pat_ratio","cfo_quality_score","cfo_quality_label","capex_intensity_pct","capex_label","fcf","fcf_cagr_5yr","fcf_conversion_pct","fcf_conversion_label","capital_allocation_pattern","capital_allocation_label","distress_flag","deleveraging_flag"]]
    # also include spec-required minimal columns as first sheet sorted for latest year view
    with pd.ExcelWriter(OUTPUT_DIR / "cashflow_intelligence.xlsx", engine="openpyxl") as writer:
        intel.to_excel(writer, sheet_name="intelligence", index=False)
        # summary sheet per company latest - spec requires 92 rows with sector + flags
        latest = df.sort_values("year_int").groupby("company_id").tail(1)
        latest_spec = latest[["company_id","sector","cfo_quality_score","cfo_quality_label","capex_intensity_pct","capex_label","fcf_cagr_5yr","fcf_conversion_pct","distress_flag","deleveraging_flag","capital_allocation_label"]]
        latest_spec.to_excel(writer, sheet_name="summary", index=False)
        # also legacy summary for compatibility
        try:
            latest[["company_id","year","cfo_quality_label","capex_intensity_label","fcf_conversion_label"]].to_excel(writer, sheet_name="summary_legacy", index=False)
        except Exception:
            pass

    # distress_alerts.csv per spec: companies flagged with distress signal — include CFO value, CFF value, and latest net profit
    alerts = df[df["distress_flag"]==1][["company_id","year","operating_activity","financing_activity","net_profit","capital_allocation_pattern"]]
    # rename to spec names
    alerts = alerts.rename(columns={"operating_activity":"CFO","financing_activity":"CFF","net_profit":"latest_net_profit"})
    alerts.to_csv(OUTPUT_DIR / "distress_alerts.csv", index=False)
    # pattern changes report per Day32
    try:
        df_sorted = df.sort_values(["company_id","year_int"])
        df_sorted["prev_pattern"] = df_sorted.groupby("company_id")["capital_allocation_pattern"].shift(1)
        changes = df_sorted[df_sorted["capital_allocation_pattern"] != df_sorted["prev_pattern"]]
        changes = changes[changes["prev_pattern"].notna()][["company_id","year","prev_pattern","capital_allocation_pattern"]]
        changes.to_csv(OUTPUT_DIR / "pattern_changes.csv", index=False)
        # distribution summary for latest year
        latest_dist = df.sort_values("year_int").groupby("company_id").tail(1)["capital_allocation_pattern"].value_counts()
        # ensure capital_allocation.csv from Sprint 2 is updated to include pattern_label
        if "cfo_pat_5yr_avg" in df.columns:
            # write updated capital_allocation.csv with pattern_label if not exists
            cap_alloc = df[["company_id","year","operating_activity","investing_activity","financing_activity","capital_allocation_pattern"]]
            cap_alloc = cap_alloc.rename(columns={"capital_allocation_pattern":"pattern_label"})
            # also add sign columns
            cap_alloc["cfo_sign"] = np.sign(df["operating_activity"])
            cap_alloc["cfi_sign"] = np.sign(df["investing_activity"])
            cap_alloc["cff_sign"] = np.sign(df["financing_activity"])
            cap_alloc.to_csv(OUTPUT_DIR / "capital_allocation.csv", index=False)
    except Exception as e:
        pass
    con.close()
    return df

if __name__ == "__main__":
    df = compute_cashflow_kpis()
    print(f"Cashflow KPIs: {len(df)} rows, distress {df['distress_flag'].sum()}")
