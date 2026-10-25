"""CAGR with 6 edge cases."""
import pathlib, sqlite3
import pandas as pd
import numpy as np

DB_PATH = pathlib.Path("data/nifty100.db")

def compute_cagr(start, end, n):
    """Returns (value, flag). Flags: OK, DECLINE_TO_LOSS, TURNAROUND, BOTH_NEGATIVE, ZERO_BASE, INSUFFICIENT"""
    if n is None or n <= 0:
        return None, "INSUFFICIENT"
    if start is None or end is None or pd.isna(start) or pd.isna(end):
        return None, "INSUFFICIENT"
    try:
        start = float(start)
        end = float(end)
        n = int(n)
    except:
        return None, "INSUFFICIENT"
    if n < 1:
        return None, "INSUFFICIENT"
    if start == 0:
        return None, "ZERO_BASE"
    if start > 0 and end > 0:
        cagr = (end / start) ** (1/n) - 1
        return cagr * 100, "OK"
    if start > 0 and end < 0:
        return None, "DECLINE_TO_LOSS"
    if start < 0 and end > 0:
        return None, "TURNAROUND"
    if start < 0 and end < 0:
        return None, "BOTH_NEGATIVE"
    if end == 0:
        # start !=0 handled above; end 0 treated as decline
        if start > 0:
            return None, "DECLINE_TO_LOSS"
        else:
            return None, "BOTH_NEGATIVE"
    return None, "INSUFFICIENT"

def compute_cagr_windows(db_path=DB_PATH):
    con = sqlite3.connect(str(db_path))
    pl = pd.read_sql("SELECT company_id, year, sales, net_profit, eps FROM profitandloss ORDER BY company_id, year", con)
    # ensure year numeric
    pl["year_int"] = pd.to_numeric(pl["year"], errors="coerce")
    # Also load FCF for FCF CAGR per Part 3
    try:
        fr_fcf = pd.read_sql("SELECT company_id, year, free_cash_flow_cr FROM financial_ratios", con)
        fr_fcf["year_int"] = pd.to_numeric(fr_fcf["year"], errors="coerce")
        has_fcf = not fr_fcf.empty and "free_cash_flow_cr" in fr_fcf.columns
    except Exception:
        fr_fcf = pd.DataFrame(columns=["company_id","year","free_cash_flow_cr","year_int"])
        has_fcf = False
    results = []
    for cid, g in pl.groupby("company_id"):
        g = g.sort_values("year_int")
        sales_map = dict(zip(g["year_int"], g["sales"]))
        pat_map = dict(zip(g["year_int"], g["net_profit"]))
        eps_map = dict(zip(g["year_int"], g["eps"]))
        # Build FCF map for this company
        if has_fcf:
            fcf_g = fr_fcf[fr_fcf["company_id"] == cid].sort_values("year_int")
            fcf_map = dict(zip(fcf_g["year_int"], fcf_g["free_cash_flow_cr"]))
        else:
            fcf_map = {}
        for _, row in g.iterrows():
            y = row["year_int"]
            rec = {"company_id": cid, "year": str(int(y)) if pd.notna(y) else row["year"]}
            for metric, m_map, prefix in [( "sales", sales_map, "revenue"), ("net_profit", pat_map, "pat"), ("eps", eps_map, "eps")]:
                for window, n in [("3yr",3),("5yr",5),("10yr",10)]:
                    start_y = y - n
                    if start_y in m_map:
                        val, flag = compute_cagr(m_map[start_y], m_map[y], n)
                        rec[f"{prefix}_cagr_{window}"] = val
                        if window == "5yr":
                            rec[f"{prefix}_cagr_5yr_flag"] = flag
                    else:
                        rec[f"{prefix}_cagr_{window}"] = None
                        if window == "5yr":
                            rec[f"{prefix}_cagr_5yr_flag"] = "INSUFFICIENT"
            # FCF CAGR per Part 3 – same 6 edge rules, using free_cash_flow_cr
            for window, n in [("3yr",3),("5yr",5),("10yr",10)]:
                start_y = y - n
                if start_y in fcf_map and y in fcf_map:
                    val, flag = compute_cagr(fcf_map[start_y], fcf_map[y], n)
                    rec[f"fcf_cagr_{window}"] = val
                    if window == "5yr":
                        rec[f"fcf_cagr_5yr_flag"] = flag
                    elif window == "3yr":
                        rec[f"fcf_cagr_3yr_flag"] = flag
                    elif window == "10yr":
                        rec[f"fcf_cagr_10yr_flag"] = flag
                else:
                    rec[f"fcf_cagr_{window}"] = None
                    if window == "5yr":
                        rec[f"fcf_cagr_5yr_flag"] = "INSUFFICIENT"
                    elif window == "3yr":
                        rec[f"fcf_cagr_3yr_flag"] = "INSUFFICIENT"
                    elif window == "10yr":
                        rec[f"fcf_cagr_10yr_flag"] = "INSUFFICIENT"
            results.append(rec)
    df = pd.DataFrame(results)
    # update financial_ratios table
    cur = con.cursor()
    cur.execute("PRAGMA table_info(financial_ratios)")
    cols = [r[1] for r in cur.fetchall()]
    # upsert via update
    for _, r in df.iterrows():
        sets = []
        params = []
        for k in ["revenue_cagr_3yr","revenue_cagr_5yr","revenue_cagr_10yr","pat_cagr_3yr","pat_cagr_5yr","pat_cagr_10yr","eps_cagr_3yr","eps_cagr_5yr","eps_cagr_10yr","fcf_cagr_3yr","fcf_cagr_5yr","fcf_cagr_10yr","revenue_cagr_5yr_flag","pat_cagr_5yr_flag","eps_cagr_5yr_flag","fcf_cagr_3yr_flag","fcf_cagr_5yr_flag","fcf_cagr_10yr_flag"]:
            if k in cols:
                sets.append(f"{k}=?")
                params.append(r.get(k))
        if not sets:
            continue
        params.extend([r["company_id"], r["year"]])
        cur.execute(f"UPDATE financial_ratios SET {', '.join(sets)} WHERE company_id=? AND year=?", params)
    con.commit()
    con.close()
    return df

if __name__ == "__main__":
    df = compute_cagr_windows()
    print(df.head())
