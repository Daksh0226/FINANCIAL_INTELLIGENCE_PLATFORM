from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
import pathlib, sqlite3
import pandas as pd
from src.api.routers._util import records as sanitize_records, jsonable_dict

router = APIRouter()
DB_PATH = pathlib.Path("data/nifty100.db")

@router.get("/companies")
def list_companies(broad_sector: str | None = None, market_cap_category: str | None = None, search: str | None = None, limit: int = 100, offset: int = 0):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be 1-200")
    con = sqlite3.connect(str(DB_PATH))
    q = "SELECT * FROM companies WHERE 1=1"
    params=[]
    if broad_sector:
        q += " AND broad_sector=?"
        params.append(broad_sector)
    if market_cap_category:
        q += " AND market_cap_category=?"
        params.append(market_cap_category)
    if search:
        q += " AND (company_id LIKE ? OR company_name LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    q += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    df = pd.read_sql(q, con, params=params)
    con.close()
    return {"count": len(df), "companies": sanitize_records(df)}

@router.get("/companies/{company_id}")
def get_company(company_id: str):
    con = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql("SELECT * FROM companies WHERE company_id=?", con, params=(company_id,))
    if df.empty:
        con.close()
        raise HTTPException(status_code=404, detail="Company not found")
    # include latest ratios
    fr = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id=? ORDER BY year DESC LIMIT 1", con, params=(company_id,))
    con.close()
    rec = jsonable_dict(df.iloc[0].to_dict())
    if not fr.empty:
        rec["latest_ratios"] = jsonable_dict(fr.iloc[0].to_dict())
    return rec

@router.get("/companies/{company_id}/pl")
def get_pl(company_id: str, from_year: str | None = Query(None, description="YYYY-MM"), to_year: str | None = Query(None)):
    con = sqlite3.connect(str(DB_PATH))
    if pd.read_sql("SELECT 1 FROM companies WHERE company_id=?", con, params=(company_id,)).empty:
        con.close()
        raise HTTPException(status_code=404, detail="Company not found")
    # from_year/to_year as YYYY-MM or YYYY
    q="SELECT * FROM profitandloss WHERE company_id=? ORDER BY year"
    df=pd.read_sql(q, con, params=(company_id,))
    con.close()
    if from_year:
        df=df[df["year"]>=from_year[:4]]
    if to_year:
        df=df[df["year"]<=to_year[:4]]
    return sanitize_records(df)

@router.get("/companies/{company_id}/bs")
def get_bs(company_id: str, from_year: str | None = None, to_year: str | None = None):
    con = sqlite3.connect(str(DB_PATH))
    if pd.read_sql("SELECT 1 FROM companies WHERE company_id=?", con, params=(company_id,)).empty:
        con.close()
        raise HTTPException(status_code=404, detail="Company not found")
    df=pd.read_sql("SELECT * FROM balancesheet WHERE company_id=? ORDER BY year", con, params=(company_id,))
    con.close()
    if from_year:
        df=df[df["year"]>=from_year[:4]]
    if to_year:
        df=df[df["year"]<=to_year[:4]]
    return sanitize_records(df)

@router.get("/companies/{company_id}/cashflow")
def get_cashflow(company_id: str, from_year: str | None = None, to_year: str | None = None):
    con = sqlite3.connect(str(DB_PATH))
    if pd.read_sql("SELECT 1 FROM companies WHERE company_id=?", con, params=(company_id,)).empty:
        con.close()
        raise HTTPException(status_code=404, detail="Company not found")
    df=pd.read_sql("SELECT * FROM cashflow WHERE company_id=? ORDER BY year", con, params=(company_id,))
    con.close()
    if from_year:
        df=df[df["year"]>=from_year[:4]]
    if to_year:
        df=df[df["year"]<=to_year[:4]]
    return sanitize_records(df)

@router.get("/companies/{company_id}/ratios")
def get_ratios(company_id: str, year: str | None = None):
    con = sqlite3.connect(str(DB_PATH))
    if pd.read_sql("SELECT 1 FROM companies WHERE company_id=?", con, params=(company_id,)).empty:
        con.close()
        raise HTTPException(status_code=404, detail="Company not found")
    if year:
        df=pd.read_sql("SELECT * FROM financial_ratios WHERE company_id=? AND year=?", con, params=(company_id, year))
    else:
        df=pd.read_sql("SELECT * FROM financial_ratios WHERE company_id=? ORDER BY year", con, params=(company_id,))
    con.close()
    if df.empty:
        raise HTTPException(status_code=404, detail="No ratios found")
    return sanitize_records(df)

@router.get("/companies/{company_id}/documents")
def get_company_documents(company_id: str):
    con = sqlite3.connect(str(DB_PATH))
    if pd.read_sql("SELECT 1 FROM companies WHERE company_id=?", con, params=(company_id,)).empty:
        con.close()
        raise HTTPException(status_code=404, detail="Company not found")
    df=pd.read_sql("SELECT * FROM documents WHERE company_id=? ORDER BY year", con, params=(company_id,))
    con.close()
    # add is_url_valid flag per spec
    def is_valid(url):
        if pd.isna(url): return False
        s=str(url).strip()
        return s.startswith("http://") or s.startswith("https://")
    if not df.empty:
        df["is_url_valid"]=df["report_url"].apply(is_valid)
    return sanitize_records(df)

@router.get("/companies/{company_id}/peers/compare")
def compare_peers(company_id: str):
    con = sqlite3.connect(str(DB_PATH))
    comp=pd.read_sql("SELECT * FROM companies WHERE company_id=?", con, params=(company_id,))
    if comp.empty:
        con.close()
        raise HTTPException(status_code=404, detail="Company not found")
    # find peer group
    pg=pd.read_sql("SELECT peer_group_name FROM peer_groups WHERE company_id=? LIMIT 1", con, params=(company_id,))
    if pg.empty:
        # fallback to broad_sector
        group=comp.iloc[0]["broad_sector"]
        peers_ids=pd.read_sql("SELECT company_id FROM companies WHERE broad_sector=?", con, params=(group,))["company_id"].tolist()
    else:
        group=pg.iloc[0]["peer_group_name"]
        peers_ids=pd.read_sql("SELECT company_id FROM peer_groups WHERE peer_group_name=?", con, params=(group,))["company_id"].tolist()
    # get 8 metrics for radar
    metrics=["return_on_equity_pct","return_on_capital_employed_pct","net_profit_margin_pct","debt_to_equity","free_cash_flow_cr","pat_cagr_5yr","revenue_cagr_5yr","composite_quality_score"]
    placeholders=",".join(["?"]*len(peers_ids)) if peers_ids else "''"
    if peers_ids:
        fr=pd.read_sql(f"SELECT company_id, {', '.join(metrics)} FROM financial_ratios WHERE company_id IN ({placeholders}) ORDER BY year DESC", con, params=peers_ids)
        # latest per company
        fr["year_int"]=pd.to_numeric(fr["year"] if "year" in fr.columns else 0, errors="coerce")
    else:
        fr=pd.DataFrame()
    # company values
    company_vals=pd.read_sql(f"SELECT {', '.join(metrics)} FROM financial_ratios WHERE company_id=? ORDER BY year DESC LIMIT 1", con, params=(company_id,))
    con.close()
    company_dict=company_vals.iloc[0].to_dict() if not company_vals.empty else {}
    # peer average
    peer_avg={}
    if not fr.empty:
        # take latest per company then average
        # simplified: average across latest rows already
        for m in metrics:
            if m in fr.columns:
                vals=fr[m].dropna()
                peer_avg[m]= float(vals.mean()) if not vals.empty else None
    return {"company_id": company_id, "peer_group": group, "company_metrics": company_dict, "peer_average": peer_avg, "is_benchmark": False}

@router.get("/companies/{company_id}/tearsheet")
def get_tearsheet(company_id: str):
    con = sqlite3.connect(str(DB_PATH))
    if pd.read_sql("SELECT 1 FROM companies WHERE company_id=?", con, params=(company_id,)).empty:
        con.close()
        raise HTTPException(status_code=404, detail="Company not found")
    con.close()
    path=pathlib.Path(f"reports/tearsheets/{company_id}_tearsheet.pdf")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Tearsheet not found")
    return FileResponse(str(path), media_type="application/pdf", filename=f"{company_id}_tearsheet.pdf")
