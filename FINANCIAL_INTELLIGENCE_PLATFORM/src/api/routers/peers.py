from fastapi import APIRouter, HTTPException
import pathlib, sqlite3, numpy as np
import pandas as pd
from src.api.routers._util import records

router = APIRouter()
DB_PATH = pathlib.Path("data/nifty100.db")

def _sanitize(val):
    if isinstance(val, float) and (pd.isna(val) or np.isinf(val)):
        return None
    return val

def _sanitize_dict(d):
    return {k: _sanitize(v) for k, v in d.items()}

@router.get("/peers/group/{group_name}")
def get_peer_group(group_name: str):
    con = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql("SELECT * FROM peer_groups WHERE peer_group_name=?", con, params=(group_name,))
    if df.empty:
        con.close()
        raise HTTPException(status_code=404, detail="Peer group not found")
    con.close()
    return {"group": group_name, "members": records(df)}

@router.get("/peers/{identifier}")
def get_peers_or_group(identifier: str):
    con = sqlite3.connect(str(DB_PATH))
    # First try as peer group name
    df_group = pd.read_sql("SELECT * FROM peer_groups WHERE peer_group_name=?", con, params=(identifier,))
    if not df_group.empty:
        try:
            # Long format: return all percentile rows for this group
            pct = pd.read_sql("SELECT * FROM peer_percentiles WHERE peer_group_name=?", con, params=(identifier,))
        except Exception:
            pct = pd.DataFrame()
        con.close()
        # Provide both long and pivoted (wide) for backward compat
        return {"group": identifier, "members": records(df_group), "percentiles_long": records(pct), "percentiles": records(pct)}
    # else treat as company_id
    c = pd.read_sql("SELECT * FROM companies WHERE company_id=?", con, params=(identifier,))
    if not c.empty:
        # Long format: get latest year for this company
        yr_row = pd.read_sql("SELECT year FROM peer_percentiles WHERE company_id=? ORDER BY year DESC LIMIT 1", con, params=(identifier,))
        if yr_row.empty:
            con.close()
            raise HTTPException(status_code=404, detail="No peer data for company")
        latest_year = yr_row.iloc[0]["year"]
        df = pd.read_sql("SELECT * FROM peer_percentiles WHERE company_id=? AND year=?", con, params=(identifier, latest_year))
        if df.empty:
            con.close()
            raise HTTPException(status_code=404, detail="No peer data for company")
        pg = df.iloc[0].get("peer_group_name")
        # Pivot long to dict {metric: {value, percentile_rank}}
        pivot = {str(row["metric"]): {"value": _sanitize(row["value"]), "percentile_rank": _sanitize(row["percentile_rank"]), "peer_group_name": _sanitize(row["peer_group_name"]), "year": _sanitize(row["year"])} for _, row in df.iterrows()}
        members = pd.DataFrame()
        if pg and pd.notna(pg):
            try:
                members = pd.read_sql("SELECT * FROM peer_percentiles WHERE peer_group_name=? AND year=?", con, params=(pg, latest_year))
            except Exception:
                members = pd.DataFrame()
        con.close()
        return {"company_id": identifier, "peer_group": _sanitize(pg), "year": latest_year, "percentiles": pivot, "percentiles_long": records(df), "peers_count": len(members) // 10 if not members.empty else 0}
    con.close()
    raise HTTPException(status_code=404, detail="Peer group or company not found")
