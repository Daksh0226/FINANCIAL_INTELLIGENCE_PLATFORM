from fastapi import APIRouter
import pathlib, sqlite3, time
router = APIRouter()
START = time.time()
DB_PATH = pathlib.Path("data/nifty100.db")
VERSION = "1.0.0"

@router.get("/health")
def health():
    # spec requires db_row_counts, uptime, version
    counts = {}
    try:
        con = sqlite3.connect(str(DB_PATH))
        cur = con.cursor()
        for tbl in ["companies","profitandloss","balancesheet","cashflow","analysis","documents","prosandcons","sectors","stock_prices","financial_ratios","peer_groups","peer_percentiles"]:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                counts[tbl] = cur.fetchone()[0]
            except Exception:
                counts[tbl] = 0
        con.close()
    except Exception:
        counts = {}
    return {"status":"ok", "db_row_counts": counts, "uptime_seconds": int(time.time()-START), "version": VERSION}

@router.get("/healthz")
def healthz():
    return {"status":"ok", "service":"nifty100"}
