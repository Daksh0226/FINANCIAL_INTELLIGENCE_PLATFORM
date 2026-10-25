from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import pathlib, sqlite3
import pandas as pd
from src.api.routers._util import records

router = APIRouter()
DB_PATH = pathlib.Path("data/nifty100.db")

@router.get("/documents")
def list_documents(limit: int = 50):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit 1-200")
    con = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql("SELECT * FROM documents LIMIT ?", con, params=(limit,))
    con.close()
    return {"count": len(df), "documents": records(df)}

@router.get("/documents/{company_id}")
def get_documents(company_id: str):
    con = sqlite3.connect(str(DB_PATH))
    c = pd.read_sql("SELECT 1 FROM companies WHERE company_id=?", con, params=(company_id,))
    if c.empty:
        con.close()
        raise HTTPException(status_code=404, detail="Company not found")
    df = pd.read_sql("SELECT * FROM documents WHERE company_id=?", con, params=(company_id,))
    con.close()
    if df.empty:
        raise HTTPException(status_code=404, detail="No documents for company")
    return {"company_id": company_id, "documents": records(df)}

@router.get("/tearsheet/{company_id}")
def download_tearsheet(company_id: str):
    con = sqlite3.connect(str(DB_PATH))
    c = pd.read_sql("SELECT 1 FROM companies WHERE company_id=?", con, params=(company_id,))
    con.close()
    if c.empty:
        raise HTTPException(status_code=404, detail="Company not found")
    path = pathlib.Path(f"reports/tearsheets/{company_id}_tearsheet.pdf")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Tearsheet not found")
    return FileResponse(str(path), media_type="application/pdf", filename=f"{company_id}_tearsheet.pdf")
