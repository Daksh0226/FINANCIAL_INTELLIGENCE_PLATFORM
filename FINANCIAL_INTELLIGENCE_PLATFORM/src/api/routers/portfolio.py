from fastapi import APIRouter, HTTPException
import pathlib, sqlite3
import pandas as pd
from src.api.routers._util import records

router = APIRouter()
DB_PATH = pathlib.Path("data/nifty100.db")
OUTPUT_DIR = pathlib.Path("output")

@router.get("/portfolio/clusters")
def get_clusters():
    path = OUTPUT_DIR / "cluster_labels.csv"
    if path.exists():
        df = pd.read_csv(path)
        return {"count": len(df), "clusters": records(df)}
    # fallback DB
    con = sqlite3.connect(str(DB_PATH))
    try:
        df = pd.read_sql("SELECT * FROM financial_ratios LIMIT 5", con)
    except:
        df = pd.DataFrame()
    con.close()
    if df.empty:
        raise HTTPException(status_code=404, detail="No cluster data")
    return {"count": len(df), "clusters": []}

@router.get("/portfolio/stats")
def get_stats():
    path = OUTPUT_DIR / "portfolio_stats.csv"
    if path.exists():
        df = pd.read_csv(path)
        return {"stats": records(df)}
    raise HTTPException(status_code=404, detail="Portfolio stats not found")
