"""Loader: reads canonical Excel files (header=1), validates, loads SQLite.
Fixes: canonical source priority, stock_prices validation, sector medians calculation."""
import sqlite3
import pathlib
import pandas as pd
import re
import random
import numpy as np
from .normaliser import normalize_year, normalize_ticker
from .validator import validate_all

DB_PATH = pathlib.Path("data/nifty100.db")
SCHEMA_PATH = pathlib.Path("db/schema.sql")
SOURCE_DIR = pathlib.Path("data/source")
PROJECT_ROOT = pathlib.Path(".")

STOCK_REQUIRED = ["company_id", "date", "close_price", "market_cap_crore", "pe_ratio", "pb_ratio", "dividend_yield"]

def read_canonical(path: pathlib.Path) -> pd.DataFrame:
    """Read canonical file with header=1, drop Unnamed columns."""
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, header=1)
        # Drop fully Unnamed columns
        df = df.loc[:, ~df.columns.astype(str).str.contains("Unnamed")]
        # If cols still look like title row, fallback to header=0 detection
        cols = [str(c).strip() for c in df.columns.astype(str)]
        if cols and (cols[0].isdigit() or cols[0].lower().startswith("unnamed")):
            df = pd.read_excel(path, header=0)
            df = df.loc[:, ~df.columns.astype(str).str.contains("Unnamed")]
        return df
    except Exception as e:
        print(f"WARN read {path}: {e}")
        return pd.DataFrame()

def validate_stock_prices(df: pd.DataFrame) -> bool:
    """Validate that df contains required stock_prices columns. Accept OHLCV with close_price."""
    if df.empty:
        print("REJECT stock_prices: empty DataFrame")
        return False
    # Check required columns present (case-insensitive, stripped)
    lower_cols = [str(c).strip().lower() for c in df.columns]
    # Accept if we have company_id, date, and close_price (OHLCV format)
    has_company = any("company" in c or "ticker" in c for c in lower_cols)
    has_date = any("date" in c for c in lower_cols)
    has_close = any("close" in c for c in lower_cols)
    if not (has_company and has_date and has_close):
        print(f"REJECT stock_prices: missing required columns - need company_id, date, close_price. Found: {list(df.columns)[:10]}")
        return False
    # Additional check: ensure not OHLCV structure without close
    if "open_price" in lower_cols and "close_price" not in lower_cols:
        print("REJECT stock_prices: detected OHLCV structure without close_price")
        return False
    print(f"VALID stock_prices: found required columns, shape {df.shape}")
    return True

def normalize_df(df: pd.DataFrame, table: str) -> pd.DataFrame:
    if df.empty:
        return df
    # Preserve row identity where it is meaningful.
    # analysis is one row per (company, period); its source "id" is the only stable
    # key for those period rows, so keep it as analysis_id instead of discarding it.
    if table == "analysis" and "id" in df.columns and "analysis_id" not in df.columns:
        df = df.rename(columns={"id": "analysis_id"})
        df["analysis_id"] = pd.to_numeric(df["analysis_id"], errors="coerce").astype("Int64")
    elif "id" in df.columns and table != "companies":
        # Drop synthetic 'id' column if present (not needed)
        df = df.drop(columns=["id"])
    elif "id" in df.columns and table == "companies":
        if "company_id" not in df.columns:
            df = df.rename(columns={"id": "company_id"})
        else:
            df = df.drop(columns=["id"])
    # Strip column names
    col_map = {c: str(c).strip() for c in df.columns}
    df = df.rename(columns=col_map)
    rename = {}
    for c in df.columns:
        lc = c.lower()
        if lc == "year":
            rename[c] = "year"
        elif lc == "annual_report":
            rename[c] = "report_url"
        elif lc == "about_company":
            rename[c] = "about"
        elif lc == "other_asset":
            rename[c] = "other_assets"
    if rename:
        df = df.rename(columns=rename)
    if table == "balancesheet" and "other_assets" in df.columns and "cwip" in df.columns:
        df["other_assets"] = df["other_assets"].fillna(0) + df["cwip"].fillna(0)
        df = df.drop(columns=["cwip"])
    elif table == "balancesheet" and "cwip" in df.columns and "other_assets" not in df.columns:
        df["other_assets"] = df["cwip"]
        df = df.drop(columns=["cwip"])
    if table == "companies" and "company_id" not in df.columns and "id" in df.columns:
        df["company_id"] = df["id"]
    # normalize company_id variants
    for col in ["company_id", "Company_ID", "Ticker", "ticker", "CompanyID", "id"]:
        if col in df.columns:
            df["company_id"] = df[col].apply(normalize_ticker)
            break
    if "company_id" in df.columns:
        df["company_id"] = df["company_id"].apply(normalize_ticker)
    if "year" in df.columns:
        df["year"] = df["year"].apply(normalize_year)
    elif "Year" in df.columns:
        df["year"] = df["Year"].apply(normalize_year)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    if table == "stock_prices" and "year" in df.columns and "date" not in df.columns:
        df["date"] = df["year"].apply(lambda x: f"{x}-03-31" if pd.notna(x) and str(x).isdigit() else normalize_year(x))
    if table == "documents" and "Annual_Report" in df.columns:
        df["report_url"] = df["Annual_Report"]
    if table == "financial_ratios" and "year" in df.columns:
        df["year"] = df["year"].apply(normalize_year)
    # sectors per-company file -> aggregate (only if canonical sectors is per-company)
    if table == "sectors" and "company_id" in df.columns:
        try:
            if "broad_sector" in df.columns:
                agg = df.groupby("broad_sector").size().reset_index(name="company_count")
                df = agg
                df["median_roe"] = None
                df["median_pe"] = None
                df["median_de"] = None
        except Exception:
            pass
    if table == "prosandcons" and "pros" in df.columns and "cons" in df.columns:
        try:
            rows=[]
            for _, r in df.iterrows():
                cid = r.get("company_id")
                if pd.isna(cid):
                    continue
                pros = str(r.get("pros","")).strip()
                cons = str(r.get("cons","")).strip()
                if pros and pros.lower() not in ["nan","none",""]:
                    rows.append({"company_id": cid, "type": "pro", "description": pros})
                if cons and cons.lower() not in ["nan","none",""]:
                    rows.append({"company_id": cid, "type": "con", "description": cons})
            df = pd.DataFrame(rows)
            if not df.empty:
                df = df.drop_duplicates(subset=["company_id","type","description"])
        except Exception as e:
            print(f"WARN prosandcons transform {e}")
    return df

def compute_sector_medians(db_path=DB_PATH):
    """Calculate median_roe, median_pe, median_de per sector deterministically."""
    con = sqlite3.connect(str(db_path))
    try:
        companies = pd.read_sql("SELECT company_id, broad_sector FROM companies", con)
        fr = pd.read_sql("SELECT company_id, year, return_on_equity_pct, debt_to_equity FROM financial_ratios", con)
        sp = pd.read_sql("SELECT company_id, date, pe_ratio FROM stock_prices", con)
    except Exception as e:
        print(f"WARN sector medians fetch: {e}")
        con.close()
        return
    # Determine latest financial year and latest stock price date
    fr["year_int"] = pd.to_numeric(fr["year"], errors="coerce")
    # latest year per spec: latest available financial year (cap at 2024 to avoid synthetic future outliers 2055 etc)
    if not fr.empty and fr["year_int"].notna().any():
        # Consider only realistic years <=2024 with sufficient coverage, fallback to max if none
        realistic = fr[fr["year_int"] <= 2024]
        if not realistic.empty and realistic["year_int"].notna().any():
            latest_year = int(realistic["year_int"].max())
        else:
            latest_year = int(fr["year_int"].max())
        latest_year_str = str(latest_year)
        print(f"Sector medians: latest financial year = {latest_year_str}")
        fr_latest = fr[fr["year"] == latest_year_str]
        # If no rows for that string (year might be stored as int), try numeric
        if fr_latest.empty:
            fr_latest = fr[fr["year_int"] == latest_year]
    else:
        fr_latest = fr

    sp["date"] = pd.to_datetime(sp["date"], errors="coerce")
    if not sp.empty and sp["date"].notna().any():
        latest_date = sp["date"].max()
        print(f"Sector medians: latest stock price date = {latest_date.date()}")
        sp_latest = sp[sp["date"] == latest_date]
    else:
        sp_latest = sp

    # Map company to sector
    comp_to_sector = dict(zip(companies["company_id"], companies["broad_sector"]))

    # Build sector groups
    # median_roe: from valid ROE values in fr_latest grouped by sector
    # median_de: from valid debt_to_equity in fr_latest
    # median_pe: from latest valid pe_ratio in sp_latest
    sectors = pd.read_sql("SELECT * FROM sectors", con)
    # Also ensure company_count matches actual companies grouping (deterministic)
    actual_counts = companies["broad_sector"].value_counts().to_dict()
    for sec_name, cnt in actual_counts.items():
        con.execute("UPDATE sectors SET company_count=? WHERE broad_sector=?", (int(cnt), sec_name))
    # Refresh sectors after count fix
    sectors = pd.read_sql("SELECT * FROM sectors", con)
    updated = 0
    for idx, row in sectors.iterrows():
        sector = row["broad_sector"]
        # companies in this sector
        cids = companies[companies["broad_sector"] == sector]["company_id"].tolist()
        if not cids:
            continue
        # ROE median
        roe_vals = fr_latest[fr_latest["company_id"].isin(cids)]["return_on_equity_pct"].dropna()
        # Filter valid: not inf, not null
        roe_vals = roe_vals.replace([np.inf, -np.inf], np.nan).dropna()
        median_roe = float(roe_vals.median()) if not roe_vals.empty else None

        # D/E median
        de_vals = fr_latest[fr_latest["company_id"].isin(cids)]["debt_to_equity"].dropna().replace([np.inf, -np.inf], np.nan).dropna()
        median_de = float(de_vals.median()) if not de_vals.empty else None

        # P/E median
        pe_vals = sp_latest[sp_latest["company_id"].isin(cids)]["pe_ratio"].dropna().replace([np.inf, -np.inf], np.nan).dropna()
        median_pe = float(pe_vals.median()) if not pe_vals.empty else None

        # Update DB
        con.execute("UPDATE sectors SET median_roe=?, median_pe=?, median_de=? WHERE broad_sector=?",
                    (median_roe, median_pe, median_de, sector))
        updated += 1
        print(f"  Sector {sector}: median_roe={median_roe}, median_pe={median_pe}, median_de={median_de} (n_roe={len(roe_vals)}, n_pe={len(pe_vals)}, n_de={len(de_vals)})")
    con.commit()
    # Verify
    df_check = pd.read_sql("SELECT * FROM sectors", con)
    print("Sector medians after update:")
    print(df_check.to_string())
    con.close()
    return updated

def load():
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    pathlib.Path("output").mkdir(parents=True, exist_ok=True)
    pathlib.Path("data").mkdir(parents=True, exist_ok=True)

    if not any(SOURCE_DIR.glob("*.xlsx")) and not any(PROJECT_ROOT.glob("*.xlsx")):
        print("No source files found — generating synthetic datasets...")
        from .generate_synthetic import generate_all
        generate_all()

    # Define canonical tables and their source files
    table_sources = {
        "companies": SOURCE_DIR / "companies.xlsx",
        "profitandloss": SOURCE_DIR / "profitandloss.xlsx",
        "balancesheet": SOURCE_DIR / "balancesheet.xlsx",
        "cashflow": SOURCE_DIR / "cashflow.xlsx",
        "analysis": SOURCE_DIR / "analysis.xlsx",
        "documents": SOURCE_DIR / "documents.xlsx",
        "prosandcons": SOURCE_DIR / "prosandcons.xlsx",
        "sectors": SOURCE_DIR / "sectors.xlsx",
        "stock_prices": SOURCE_DIR / "stock_prices.xlsx",
        "peer_groups": SOURCE_DIR / "peer_groups.xlsx",
        # financial_ratios is derived, not loaded directly from seed (empty)
    }

    dfs = {}
    audit = []

    # Load market_cap.xlsx for valuation data (yearly)
    market_cap_df = pd.DataFrame()
    market_cap_path = SOURCE_DIR / "market_cap.xlsx"
    if market_cap_path.exists():
        market_cap_raw = read_canonical(market_cap_path)
        if not market_cap_raw.empty:
            market_cap_raw = market_cap_raw.loc[:, ~market_cap_raw.columns.astype(str).str.contains("Unnamed")]
            market_cap_raw = market_cap_raw.rename(columns={"dividend_yield_pct": "dividend_yield"})
            market_cap_raw['company_id'] = market_cap_raw['company_id'].apply(normalize_ticker)
            market_cap_raw['year'] = market_cap_raw['year'].apply(normalize_year)
            market_cap_df = market_cap_raw[['company_id', 'year', 'market_cap_crore', 'pe_ratio', 'pb_ratio', 'dividend_yield']].copy()
            print(f"Loaded market_cap.xlsx: {len(market_cap_df)} rows")

    # Load canonical sources first with validation
    for table, path in table_sources.items():
        if table == "stock_prices":
            # Special validation for stock_prices - accept OHLCV format
            if path.exists():
                df_raw = read_canonical(path)
                if validate_stock_prices(df_raw):
                    df = normalize_df(df_raw, table)
                    # Handle OHLCV format: columns are idx, company_id, date, open, high, low, close, volume, extra
                    # Rename to standard format
                    lower_cols = [str(c).strip().lower() for c in df.columns]
                    if "open" in lower_cols and "high" in lower_cols and "low" in lower_cols and "close" in lower_cols:
                        # This is OHLCV format
                        df.columns = ['idx', 'company_id', 'date', 'open_price', 'high_price', 'low_price', 'close_price', 'volume', 'extra'] + list(df.columns[9:])
                    # Ensure we have required columns
                    if "company_id" in df.columns and "date" in df.columns and "close_price" in df.columns:
                        df = df[["company_id", "date", "close_price"]].copy()
                        df["company_id"] = df["company_id"].apply(normalize_ticker)
                        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
                        df = df.dropna(subset=["company_id", "date"])
                        # Merge with market_cap data (yearly) - assign year based on date
                        if not market_cap_df.empty:
                            df["year"] = pd.to_datetime(df["date"]).dt.year.astype(str)
                            market_cap_df["year"] = market_cap_df["year"].astype(str)
                            df = df.merge(market_cap_df, on=["company_id", "year"], how="left")
                            df = df.drop(columns=["year"])
                        else:
                            df["market_cap_crore"] = None
                            df["pe_ratio"] = None
                            df["pb_ratio"] = None
                            df["dividend_yield"] = None
                        # dedup
                        df = df.drop_duplicates(subset=["company_id","date"], keep="last")
                        dfs[table] = df
                        audit.append([path.name, table, len(df_raw), len(df), "canonical valid"])
                        print(f"Loaded CANONICAL {path.name} -> {table}: {len(df)} rows (validated)")
                    else:
                        print(f"REJECTED canonical {path.name} for {table} - missing required columns after parsing")
                        dfs[table] = pd.DataFrame()
                else:
                    print(f"REJECTED canonical {path.name} for {table} - not loaded")
                    dfs[table] = pd.DataFrame()
            else:
                print(f"Canonical {path} not found for {table}")
                dfs[table] = pd.DataFrame()
            continue

        # For other tables: load canonical if exists and non-empty
        if path.exists():
            df_raw = read_canonical(path)
            # For financial_ratios seed, it's empty (0 rows) - skip
            if df_raw.empty and table not in ["sectors"]:
                print(f"SKIP {path.name} -> {table}: empty (0 rows) - will be derived")
                # Check for prefixed alternative with real data (e.g., financial_ratios)
                if table == "peer_groups":
                    # Check if canonical has valid FK
                    # For now, skip empty case
                    pass
                continue
            df = normalize_df(df_raw, table)
            # dedup with correct PK per table
            if "company_id" in df.columns:
                df = df[df["company_id"].notna() & (df["company_id"] != "")]
                if table == "peer_groups":
                    # PK is (peer_group_name, company_id)
                    if "peer_group_name" in df.columns:
                        df = df.drop_duplicates(subset=["peer_group_name","company_id"], keep="last")
                    else:
                        df = df.drop_duplicates(subset=["company_id"], keep="last")
                elif table == "prosandcons":
                    if {"company_id","type","description"}.issubset(df.columns):
                        df = df.drop_duplicates(subset=["company_id","type","description"], keep="last")
                    else:
                        df = df.drop_duplicates(subset=["company_id"], keep="last")
                elif table == "sectors":
                    if "broad_sector" in df.columns:
                        df = df.drop_duplicates(subset=["broad_sector"], keep="last")
                    else:
                        df = df.drop_duplicates(subset=["company_id"], keep="last")
                elif table == "analysis" and "analysis_id" in df.columns:
                    # Multiple period rows per company are legitimate; dedup on the
                    # period key only, never on company_id alone.
                    df = df.dropna(subset=["analysis_id"])
                    df = df.drop_duplicates(subset=["analysis_id"], keep="last")
                elif "year" in df.columns:
                    df = df.drop_duplicates(subset=["company_id","year"], keep="last")
                elif "date" in df.columns:
                    df = df.drop_duplicates(subset=["company_id","date"], keep="last")
                else:
                    df = df.drop_duplicates(subset=["company_id"], keep="last")
            dfs[table] = df
            audit.append([path.name, table, len(df_raw), len(df), "canonical"])
            print(f"Loaded CANONICAL {path.name} -> {table}: {len(df)} rows")
        else:
            # Try to find prefixed file only if canonical missing, with validation
            found = None
            for cand in list(PROJECT_ROOT.glob(f"*{table}*.xlsx")) + list(SOURCE_DIR.glob(f"*{table}*.xlsx")):
                if cand.exists() and cand.stat().st_size > 1000:
                    found = cand
                    break
            if found:
                # For stock_prices we already handled, for peer_groups validate FK
                df_raw = read_canonical(found)
                df = normalize_df(df_raw, table)
                dfs[table] = df
                audit.append([found.name, table, len(df_raw), len(df), "prefixed fallback"])
                print(f"Loaded FALLBACK {found.name} -> {table}: {len(df)} rows")
            else:
                print(f"No source file for {table}, skipping")

    # Handle financial_ratios: if seed is empty, we will compute via ratios.py after loading base tables
    # But if prefixed financial_ratios.xlsx exists with real data, we could load it as base
    # Check prefixed financial_ratios (17887...)
    fin_pref = list(PROJECT_ROOT.glob("*financial_ratios*.xlsx"))
    if "financial_ratios" not in dfs or dfs.get("financial_ratios", pd.DataFrame()).empty:
        for cand in fin_pref:
            # Check if it's the seed (empty) vs real with data
            if cand.name.endswith("financial_ratios_seed.xlsx"):
                continue
            if cand.exists():
                # Read with header 0 (prefixed file has header 0)
                try:
                    df_raw = pd.read_excel(cand, header=0)
                    df_raw = df_raw.loc[:, ~df_raw.columns.astype(str).str.contains("Unnamed")]
                    if not df_raw.empty and "company_id" in df_raw.columns:
                        df = normalize_df(df_raw, "financial_ratios")
                        if not df.empty:
                            dfs["financial_ratios"] = df
                            audit.append([cand.name, "financial_ratios", len(df_raw), len(df), "prefixed financial_ratios"])
                            print(f"Loaded PREFX {cand.name} -> financial_ratios: {len(df)} rows (will be used as base before recompute)")
                            break
                except Exception as e:
                    print(f"WARN loading prefixed financial_ratios {cand}: {e}")

    # Canonical company universe = union of company_ids across all canonical sources.
    #
    # companies.xlsx alone carries only 92 of the 100 ids that appear in the financial
    # statements. The 8 missing ones (ULTRACEMCO, UNIONBANK, UNITDSPR, VBL, VEDL,
    # WIPRO, ZOMATO, ZYDUSLIFE) are genuine index members with real P&L/balance sheet/
    # cashflow/documents/analysis rows, so dropping them silently discarded valid data
    # (this is what removed WIPRO's analysis rows). Promote them into the master
    # instead, which keeps every source row and leaves the FK filter below a no-op.
    if "companies" in dfs and not dfs["companies"].empty:
        comp_df = dfs["companies"]
        known = set(comp_df["company_id"].dropna().unique().tolist())
        referenced = set()
        for t in ["profitandloss","balancesheet","cashflow","analysis","documents","prosandcons","peer_groups","stock_prices","financial_ratios"]:
            if t in dfs and not dfs[t].empty and "company_id" in dfs[t].columns:
                referenced |= set(dfs[t]["company_id"].dropna().unique().tolist())
        orphans = sorted(referenced - known)
        if orphans:
            # No legal name exists in any canonical source for these ids, and inventing
            # one would fabricate data. company_name falls back to the company_id itself.
            add = pd.DataFrame([{
                "company_id": cid,
                "company_name": cid,
                "nse_ticker": cid,
                "bse_ticker": cid,
            } for cid in orphans])
            dfs["companies"] = pd.concat([comp_df, add], ignore_index=True)
            print(f"Expanded canonical companies: {len(known)} -> {len(known) + len(orphans)}")
            print(f"  Promoted (present in source data, absent from companies.xlsx): {orphans}")

    # Ensure FK integrity: filter child tables to only include company_ids present in companies
    if "companies" in dfs and not dfs["companies"].empty:
        parent_ids = set(dfs["companies"]["company_id"].dropna().unique().tolist())
        for t in ["profitandloss","balancesheet","cashflow","analysis","documents","prosandcons","peer_groups","stock_prices","financial_ratios"]:
            if t in dfs and not dfs[t].empty and "company_id" in dfs[t].columns:
                before = len(dfs[t])
                dfs[t] = dfs[t][dfs[t]["company_id"].isin(parent_ids)]
                after = len(dfs[t])
                if before != after:
                    print(f"  Filtered {t}: {before} -> {after} (removed {before-after} FK mismatch)")

    # Merge sector data into companies (broad_sector, sub_sector, market_cap_category)
    # Read raw sectors data before normalization (which aggregates it)
    sectors_raw_path = SOURCE_DIR / "sectors.xlsx"
    if "companies" in dfs and not dfs["companies"].empty and sectors_raw_path.exists():
        sectors_raw = read_canonical(sectors_raw_path)
        if "company_id" in sectors_raw.columns and "broad_sector" in sectors_raw.columns:
            sector_cols = ["company_id", "broad_sector"]
            if "sub_sector" in sectors_raw.columns:
                sector_cols.append("sub_sector")
            if "market_cap_category" in sectors_raw.columns:
                sector_cols.append("market_cap_category")
            sector_info = sectors_raw[sector_cols].drop_duplicates(subset=["company_id"], keep="last")
            # normalize company_id
            sector_info["company_id"] = sector_info["company_id"].apply(normalize_ticker)
            dfs["companies"] = dfs["companies"].merge(sector_info, on="company_id", how="left")
            print(f"Merged sector info into companies: {len(sector_info)} sectors")

    # Extract nse_ticker and bse_ticker from profile URLs
    if "companies" in dfs and not dfs["companies"].empty:
        df = dfs["companies"]
        # Use company_id as ticker if no explicit ticker columns
        if "nse_ticker" not in df.columns:
            df["nse_ticker"] = df["company_id"]
        if "bse_ticker" not in df.columns:
            df["bse_ticker"] = df["company_id"]
        # If nse_profile/bse_profile exist, extract ticker from URL
        if "nse_profile" in df.columns:
            def extract_ticker(url):
                if pd.isna(url):
                    return None
                import re
                m = re.search(r"symbol=([A-Z0-9]+)", str(url))
                return m.group(1) if m else None
            df["nse_ticker"] = df["nse_profile"].apply(extract_ticker).fillna(df["company_id"])
        if "bse_profile" in df.columns:
            def extract_ticker(url):
                if pd.isna(url):
                    return None
                import re
                m = re.search(r"/([A-Z0-9]+)/\d+/", str(url))
                return m.group(1) if m else None
            df["bse_ticker"] = df["bse_profile"].apply(extract_ticker).fillna(df["company_id"])
        dfs["companies"] = df

    # Fix companies columns - drop extra columns not in schema
    if "companies" in dfs and not dfs["companies"].empty:
        df = dfs["companies"]
        keep_cols = ["company_id","company_name","broad_sector","sub_sector","market_cap_category","nse_ticker","bse_ticker","roe_percentage","roce_percentage","about"]
        extra_cols = [c for c in df.columns if c not in keep_cols]
        if extra_cols:
            df = df.drop(columns=extra_cols)
        dfs["companies"] = df
        print(f"Fixed companies columns: {list(dfs['companies'].columns)}")

    # Fix documents URLs before load
    if "documents" in dfs and not dfs["documents"].empty and "report_url" in dfs["documents"].columns:
        def fix_url(x):
            if pd.isna(x):
                return None
            s = str(x).strip()
            if not s or s.lower() in ["null","nan","none","na","n/a","untitled"]:
                return None
            if s.startswith("bseindia.com"):
                return "https://" + s
            if s.startswith("//"):
                return "https:" + s
            if s.endswith(".pdf") and "/" not in s and not s.startswith("http"):
                return None
            if not (s.startswith("http://") or s.startswith("https://")):
                if "bseindia.com" in s:
                    return "https://" + s.lstrip("/")
                return None
            return s
        dfs["documents"]["report_url"] = dfs["documents"]["report_url"].apply(fix_url)

    # Fix cashflow net_cash_flow
    if "cashflow" in dfs and not dfs["cashflow"].empty:
        if {"operating_activity","investing_activity","financing_activity","net_cash_flow"}.issubset(dfs["cashflow"].columns):
            dfs["cashflow"]["net_cash_flow"] = dfs["cashflow"]["operating_activity"].fillna(0) + dfs["cashflow"]["investing_activity"].fillna(0) + dfs["cashflow"]["financing_activity"].fillna(0)

    # Fix column name mismatches for profitandloss
    if "profitandloss" in dfs and not dfs["profitandloss"].empty:
        df = dfs["profitandloss"]
        if "tax_percentage" in df.columns and "tax" not in df.columns:
            df = df.rename(columns={"tax_percentage": "tax"})
        if "dividend_payout" in df.columns and "dividend_payout_ratio" not in df.columns:
            df = df.rename(columns={"dividend_payout": "dividend_payout_ratio"})
        # Handle TTM rows: keep them with "TTM" as year instead of dropping
        if "year" in df.columns:
            before = len(df)
            # Fill TTM/null years with "TTM" string to keep them
            ttm_mask = df["year"].isna()
            if ttm_mask.any():
                df.loc[ttm_mask, "year"] = "TTM"
                filled = ttm_mask.sum()
                if filled:
                    print(f"  Kept {filled} TTM rows in profitandloss with year='TTM'")
            # Drop any remaining rows with null year
            before = len(df)
            df = df[df["year"].notna()]
            after = len(df)
            if before != after:
                print(f"  Dropped {before-after} rows with null year from profitandloss")
        # Drop columns not in schema
        extra_cols = [c for c in df.columns if c not in ["company_id","year","sales","operating_profit","opm_percentage","other_income","interest","depreciation","profit_before_tax","tax","net_profit","eps","dividend_payout_ratio"]]
        if extra_cols:
            df = df.drop(columns=extra_cols)
        dfs["profitandloss"] = df

    # Fix column name mismatches for balancesheet
    if "balancesheet" in dfs and not dfs["balancesheet"].empty:
        df = dfs["balancesheet"]
        if "other_asset" in df.columns and "other_assets" not in df.columns:
            df = df.rename(columns={"other_asset": "other_assets"})
        extra_cols = [c for c in df.columns if c not in ["company_id","year","equity_capital","reserves","borrowings","other_liabilities","total_liabilities","fixed_assets","investments","other_assets","total_assets"]]
        if extra_cols:
            df = df.drop(columns=extra_cols)
        dfs["balancesheet"] = df

    # Fix column name mismatches for cashflow
    if "cashflow" in dfs and not dfs["cashflow"].empty:
        df = dfs["cashflow"]
        extra_cols = [c for c in df.columns if c not in ["company_id","year","operating_activity","investing_activity","financing_activity","net_cash_flow"]]
        if extra_cols:
            df = df.drop(columns=extra_cols)
        dfs["cashflow"] = df

    # Load stock_prices by merging OHLCV with market_cap data
    if "stock_prices" in dfs and dfs["stock_prices"].empty:
        ohlcv_path = SOURCE_DIR / "stock_prices.xlsx"
        mc_path = SOURCE_DIR / "market_cap.xlsx"
        if ohlcv_path.exists() and mc_path.exists():
            print("Merging OHLCV stock_prices with market_cap data...")
            ohlcv_raw = read_canonical(ohlcv_path)
            mc_raw = read_canonical(mc_path)
            # Normalize both
            ohlcv = normalize_df(ohlcv_raw, "stock_prices")
            mc = normalize_df(mc_raw, "market_cap")
            if "year" in mc.columns:
                mc["date"] = mc["year"].apply(lambda x: f"{x}-03-31" if pd.notna(x) and str(x).isdigit() else normalize_year(x))
            # Merge on company_id + date
            if "company_id" in ohlcv.columns and "date" in ohlcv.columns and "company_id" in mc.columns and "date" in mc.columns:
                ohlcv["company_id"] = ohlcv["company_id"].apply(normalize_ticker)
                mc["company_id"] = mc["company_id"].apply(normalize_ticker)
                ohlcv["date"] = pd.to_datetime(ohlcv["date"], errors="coerce").dt.strftime("%Y-%m-%d")
                mc["date"] = pd.to_datetime(mc["date"], errors="coerce").dt.strftime("%Y-%m-%d")
                merged = pd.merge(ohlcv, mc[["company_id","date","market_cap_crore","pe_ratio","pb_ratio","dividend_yield_pct"]], 
                                  on=["company_id","date"], how="left")
                if "dividend_yield_pct" in merged.columns and "dividend_yield" not in merged.columns:
                    merged = merged.rename(columns={"dividend_yield_pct": "dividend_yield"})
                # Drop extra cols
                keep_cols = ["company_id","date","close_price","market_cap_crore","pe_ratio","pb_ratio","dividend_yield"]
                merged = merged[[c for c in keep_cols if c in merged.columns]]
                if len(merged) > 0:
                    dfs["stock_prices"] = merged
                    print(f"Loaded stock_prices (merged): {len(merged)} rows")

    # Validate (light)
    try:
        failures = validate_all(dfs)
        failures.to_csv("output/validation_failures.csv", index=False)
        print(f"Validation failures: {len(failures)} -> output/validation_failures.csv")
        if not failures.empty:
            print(failures['severity'].value_counts().to_dict())
            print(failures['rule_id'].value_counts().to_dict())
    except Exception as e:
        print(f"WARN validate: {e}")

    # Init DB - drop and recreate from schema
    if SCHEMA_PATH.exists():
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
    else:
        sql = ""
    if DB_PATH.exists():
        try:
            DB_PATH.unlink()
        except:
            pass
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=OFF")
    if sql:
        conn.executescript(sql)
    order = ["companies","sectors","profitandloss","balancesheet","cashflow","analysis","documents","prosandcons","peer_groups","stock_prices","financial_ratios"]
    for table in order:
        df = dfs.get(table)
        if df is None or df.empty:
            # For financial_ratios, allow empty - will be populated by ratios.py
            if table == "financial_ratios":
                print(f"SKIP {table}: empty (will be computed)")
                continue
            print(f"SKIP {table}: empty")
            continue
        try:
            cur = conn.execute(f"SELECT * FROM {table} LIMIT 0")
            schema_cols = [d[0] for d in cur.description] if cur.description else list(df.columns)
            df_to_load = df[[c for c in schema_cols if c in df.columns]].copy()
            if table == "companies":
                if "company_name" not in df_to_load.columns and "company_name" in df.columns:
                    df_to_load["company_name"] = df["company_name"]
                df_to_load = df_to_load.reindex(columns=schema_cols)
            # Ensure required columns for stock_prices are present, else fill with None (should not happen)
            print(f"  Loading {table}: {len(df_to_load)} rows, cols: {list(df_to_load.columns)}")
            df_to_load.to_sql(table, conn, if_exists="append", index=False)
            print(f"Loaded {table}: {len(df_to_load)} rows")
        except Exception as e:
            print(f"ERROR loading {table}: {e}")
            import traceback; traceback.print_exc()
            try:
                print(f"  Retrying with original df: {len(df)} rows, cols: {list(df.columns)}")
                df.to_sql(table, conn, if_exists="append", index=False)
                print(f"Retry loaded {table}")
            except Exception as e2:
                print(f"FAILED {table}: {e2}")
                import traceback; traceback.print_exc()

    conn.commit()
    cur = conn.cursor()
    audit_rows = []
    for table in ["companies","profitandloss","balancesheet","cashflow","analysis","documents","prosandcons","sectors","stock_prices","financial_ratios","peer_groups"]:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            cnt = cur.fetchone()[0]
        except Exception as e:
            print(f"AUDIT err {table}: {e}")
            cnt = 0
        audit_rows.append([table, cnt])
        print(f"AUDIT {table}: {cnt}")
    pd.DataFrame(audit_rows, columns=["table","row_count"]).to_csv("output/load_audit.csv", index=False)
    pd.DataFrame(audit, columns=["file","table","before","after","note"]).to_csv("output/load_audit_detailed.csv", index=False)
    print("Load audit -> output/load_audit.csv + detailed")
    cur.execute("PRAGMA foreign_key_check")
    fk = cur.fetchall()
    print(f"FK check rows: {len(fk)} -> {fk[:5]}")
    conn.close()

    # Post-load computations: financial_ratios, cagr, CFO quality, composite, sector medians, peer percentiles
    try:
        from src.analytics.ratios import compute_all_ratios, compute_cfo_quality_scores, compute_composite_and_sector_scores
        from src.analytics.cagr import compute_cagr_windows
        print("Computing financial ratios...")
        out = compute_all_ratios()
        print(f"Ratios computed: {len(out)} rows")
        print("Computing CAGR (including FCF CAGR)...")
        cagr_df = compute_cagr_windows()
        print(f"CAGR computed: {len(cagr_df)} rows")
        print("Computing CFO Quality Scores...")
        cfo_df = compute_cfo_quality_scores()
        print(f"CFO Quality computed: {len(cfo_df)} rows")
        print("Computing Composite and Sector-Relative Scores...")
        comp_df = compute_composite_and_sector_scores()
        print(f"Composite/Sector computed: {len(comp_df)} rows")
        # Also run cashflow KPIs for other outputs (distress, pattern) – uses same CFO labels
        try:
            from src.analytics.cashflow_kpis import compute_cashflow_kpis
            compute_cashflow_kpis()
            print("Cashflow KPIs computed")
        except Exception as e2:
            print(f"WARN cashflow_kpis: {e2}")
    except Exception as e:
        print(f"WARN ratios/cagr/cfo/composite: {e}")
        import traceback; traceback.print_exc()

    # Compute sector medians deterministically
    try:
        print("Computing sector medians...")
        compute_sector_medians()
    except Exception as e:
        print(f"WARN sector medians: {e}")
        import traceback; traceback.print_exc()

    # Compute peer percentiles with corrected schema
    try:
        from src.analytics.peer import compute_peer_percentiles
        print("Computing peer percentiles (long format)...")
        pct_df = compute_peer_percentiles()
        print(f"Peer percentiles computed: {len(pct_df)} rows")
    except Exception as e:
        print(f"WARN peer percentiles: {e}")
        import traceback; traceback.print_exc()

    print("Load complete.")

if __name__ == "__main__":
    load()
