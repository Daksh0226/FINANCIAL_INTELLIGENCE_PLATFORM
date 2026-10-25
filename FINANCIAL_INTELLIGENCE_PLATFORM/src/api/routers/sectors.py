from fastapi import APIRouter, HTTPException
import pathlib, sqlite3
import pandas as pd
from src.api.routers._util import records

router = APIRouter()
DB_PATH = pathlib.Path("data/nifty100.db")

@router.get("/sectors")
def list_sectors():
    con = sqlite3.connect(str(DB_PATH))
    # Use canonical sectors table with calculated medians (prefer sectors table)
    try:
        df = pd.read_sql("SELECT broad_sector, company_count, median_roe, median_pe, median_de FROM sectors", con)
        if df.empty or df["median_roe"].isna().all():
            # Fallback to companies grouping
            df = pd.read_sql("SELECT broad_sector, COUNT(*) as company_count FROM companies GROUP BY broad_sector", con)
            df["median_roe"] = None
            df["median_pe"] = None
            df["median_de"] = None
    except Exception:
        df = pd.read_sql("SELECT broad_sector, COUNT(*) as company_count FROM companies GROUP BY broad_sector", con)
    con.close()
    return {"count": len(df), "sectors": records(df)}

@router.get("/sectors/{sector_name}")
def get_sector(sector_name: str):
    con = sqlite3.connect(str(DB_PATH))
    # First check sectors table for canonical medians
    sec_row = pd.read_sql("SELECT * FROM sectors WHERE broad_sector=?", con, params=(sector_name,))
    comps = pd.read_sql("SELECT * FROM companies WHERE broad_sector=?", con, params=(sector_name,))
    if comps.empty and sec_row.empty:
        con.close()
        raise HTTPException(status_code=404, detail="Sector not found")
    # Provide medians from sectors table (calculated)
    if not sec_row.empty:
        medians = {"median_roe": sec_row.iloc[0]["median_roe"] if pd.notna(sec_row.iloc[0]["median_roe"]) else None,
                   "median_pe": sec_row.iloc[0]["median_pe"] if pd.notna(sec_row.iloc[0]["median_pe"]) else None,
                   "median_de": sec_row.iloc[0]["median_de"] if pd.notna(sec_row.iloc[0]["median_de"]) else None,
                   "company_count": int(sec_row.iloc[0]["company_count"]) if pd.notna(sec_row.iloc[0]["company_count"]) else len(comps)}
    else:
        medians = {}
    cids = comps["company_id"].tolist()
    if cids:
        placeholders = ",".join(["?"]*len(cids))
        fr = pd.read_sql(f"SELECT AVG(return_on_equity_pct) as avg_roe, AVG(debt_to_equity) as avg_de FROM financial_ratios WHERE company_id IN ({placeholders})", con, params=cids)
        stats = fr.iloc[0].to_dict() if not fr.empty else {}
        # Merge medians, prefer medians over avgs
        stats.update(medians)
    else:
        stats = medians
    # sanitize NaNs
    for k, v in list(stats.items()):
        if isinstance(v, float) and (pd.isna(v) or v in (float("inf"), float("-inf"))):
            stats[k] = None
    con.close()
    return {"sector": sector_name, "companies": records(comps), "stats": stats, "medians": medians}

@router.get("/sectors/{sector_name}/companies")
def get_sector_companies(sector_name: str):
    return get_sector(sector_name)
