from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import pathlib, numpy as np, pandas as pd
from src.screener.engine import screen, load_universe, composite_quality_score
from src.api.routers._util import records as _records

router = APIRouter()

def sanitize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.replace([np.inf, -np.inf], None)
    df = df.astype(object).where(pd.notna(df), None)
    return df

class ScreenRequest(BaseModel):
    preset: str | None = None
    filters: dict | None = None

@router.get("/screener")
def screener_get(preset: str | None = None, min_roe: float | None = None, max_de: float | None = None, min_fcf: float | None = None, sector: str | None = None, min_rev_cagr_5yr: float | None = None, min_pat_cagr_5yr: float | None = None, max_pe: float | None = None, min_opm: float | None = None, max_pb: float | None = None, min_div_yield: float | None = None, min_icr: float | None = None, min_evebitda: float | None = None):
    # Build filters dict from query params
    filters={}
    param_map={
        "return_on_equity_pct": min_roe,
        "debt_to_equity": max_de,
        "free_cash_flow_cr": min_fcf,
        "revenue_cagr_5yr": min_rev_cagr_5yr,
        "pat_cagr_5yr": min_pat_cagr_5yr,
        "pe_ratio": max_pe,
        "operating_profit_margin_pct": min_opm,
        "pb_ratio": max_pb,
        "dividend_yield": min_div_yield,
        "interest_coverage": min_icr,
    }
    # Validate invalid values - raise 400 if negative where not allowed or nonsensical
    for k,v in param_map.items():
        if v is not None:
            if k in ["debt_to_equity","pe_ratio","pb_ratio"] and v < 0:
                raise HTTPException(status_code=400, detail=f"Invalid {k}={v}")
            if k=="return_on_equity_pct" and (v < -100 or v>100):
                raise HTTPException(status_code=400, detail=f"Invalid {k}={v}")
    try:
        # Use preset or custom filters
        if min_roe is not None or max_de is not None or min_fcf is not None or min_rev_cagr_5yr is not None or min_pat_cagr_5yr is not None or max_pe is not None:
            # build filters dict for apply_filters logic: need to handle min/max per metric
            df=load_universe()
            # apply each filter manually
            if min_roe is not None:
                df=df[(df["return_on_equity_pct"]>=min_roe) | (df["broad_sector"]=="Financials" and False)]  # keep only >=
            if max_de is not None:
                # skip Financials per spec
                mask_fin=df["broad_sector"]=="Financials"
                cond=(df["debt_to_equity"]<=max_de) | df["debt_to_equity"].isna() | mask_fin
                df=df[cond]
            if min_fcf is not None:
                df=df[df["free_cash_flow_cr"]>=min_fcf]
            if min_rev_cagr_5yr is not None:
                df=df[df["revenue_cagr_5yr"]>=min_rev_cagr_5yr]
            if min_pat_cagr_5yr is not None:
                df=df[df["pat_cagr_5yr"]>=min_pat_cagr_5yr]
            if max_pe is not None:
                # pe_ratio in universe via market cap? use load_universe pe_ratio may be None - treat as pass
                if "pe_ratio" in df.columns:
                    df=df[(df["pe_ratio"]<=max_pe) | df["pe_ratio"].isna()]
            if sector is not None:
                df=df[df["broad_sector"]==sector]
        elif preset:
            df = screen(preset=preset)
        else:
            df=load_universe()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    df["composite_quality_score"] = composite_quality_score(df)
    df=df.sort_values("composite_quality_score", ascending=False)
    out = sanitize(df.head(100))
    # to_dict with None instead of NaN
    return {"count": len(df), "results": out.to_dict(orient="records")}

@router.post("/screener/screen")
def screener_post(req: ScreenRequest):
    if req.preset and req.filters:
        raise HTTPException(status_code=400, detail="Provide either preset or filters, not both")
    try:
        df = screen(preset=req.preset, filters=req.filters)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    df["composite_quality_score"] = composite_quality_score(df)
    out = sanitize(df)
    return {"count": len(df), "results": out.to_dict(orient="records")}
