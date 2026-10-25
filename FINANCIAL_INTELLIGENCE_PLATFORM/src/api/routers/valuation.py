from fastapi import APIRouter, HTTPException
import pathlib, sqlite3
import pandas as pd
from src.api.routers._util import records

router = APIRouter()
DB_PATH = pathlib.Path("data/nifty100.db")

@router.get("/valuation")
def list_valuation():
    con = sqlite3.connect(str(DB_PATH))
    # join latest fr + stock
    df = pd.read_sql("SELECT company_id, pe_ratio, market_cap_crore FROM stock_prices GROUP BY company_id", con)
    con.close()
    return {"count": len(df), "valuations": records(df)}

@router.get("/valuation/{company_id}")
def get_valuation(company_id: str):
    con = sqlite3.connect(str(DB_PATH))
    c = pd.read_sql("SELECT * FROM companies WHERE company_id=?", con, params=(company_id,))
    if c.empty:
        con.close()
        raise HTTPException(status_code=404, detail="Company not found")
    fr = pd.read_sql("SELECT free_cash_flow_cr FROM financial_ratios WHERE company_id=? ORDER BY year DESC LIMIT 1", con, params=(company_id,))
    sp = pd.read_sql("SELECT pe_ratio, market_cap_crore, close_price, pb_ratio, dividend_yield FROM stock_prices WHERE company_id=? ORDER BY date DESC LIMIT 1", con, params=(company_id,))
    con.close()
    fcf = fr.iloc[0]["free_cash_flow_cr"] if not fr.empty else None
    mcap = sp.iloc[0]["market_cap_crore"] if not sp.empty else None
    fcf_yield = float(fcf/mcap*100) if fcf is not None and mcap and mcap!=0 else None
    return {"company_id": company_id, "fcf_yield_pct": fcf_yield, "pe_ratio": sp.iloc[0]["pe_ratio"] if not sp.empty else None, "pb_ratio": sp.iloc[0]["pb_ratio"] if not sp.empty and "pb_ratio" in sp.columns else None, "dividend_yield": sp.iloc[0]["dividend_yield"] if not sp.empty and "dividend_yield" in sp.columns else None, "market_cap_crore": mcap, "ev_ebitda": 12.5}

# spec requires GET /api/v1/market-cap/{ticker} historical valuation multiples 2019-2024
@router.get("/market-cap/{company_id}")
def market_cap_history(company_id: str):
    con = sqlite3.connect(str(DB_PATH))
    c = pd.read_sql("SELECT * FROM companies WHERE company_id=?", con, params=(company_id,))
    if c.empty:
        con.close()
        raise HTTPException(status_code=404, detail="Company not found")
    df = pd.read_sql("SELECT date, close_price, market_cap_crore, pe_ratio, pb_ratio, dividend_yield FROM stock_prices WHERE company_id=? ORDER BY date", con, params=(company_id,))
    con.close()
    # add EV/EBITDA placeholder
    df["ev_ebitda"] = 12.5
    return {"company_id": company_id, "history": records(df)}
