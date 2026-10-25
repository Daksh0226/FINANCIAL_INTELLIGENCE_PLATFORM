import sqlite3
import pandas as pd
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter

DB_PATH = Path("data/nifty100.db")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Color fills
GREEN_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
YELLOW_FILL = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
RED_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
GOLD_FILL = PatternFill(start_color="FFD966", end_color="FFD966", fill_type="solid")

def generate_peer_comparison():
    con = sqlite3.connect(str(DB_PATH))
    
    # Get peer groups
    pg = pd.read_sql("SELECT * FROM peer_groups", con)
    peer_groups = pg["peer_group_name"].unique()
    print(f"Found {len(peer_groups)} peer groups: {list(peer_groups)}")
    
    # Get company names
    companies = pd.read_sql("SELECT company_id, company_name, broad_sector FROM companies", con)
    comp_name_map = dict(zip(companies.company_id, companies.company_name))
    comp_sector_map = dict(zip(companies.company_id, companies.broad_sector))
    
    # Get financial ratios for latest year (for metric values)
    fr = pd.read_sql("SELECT * FROM financial_ratios", con)
    fr["year_int"] = pd.to_numeric(fr["year"], errors="coerce")
    latest_fr = fr.sort_values("year_int").groupby("company_id").tail(1)
    
    # Metrics to include (10 metrics from peer.py + composite)
    metrics = [
        "net_profit_margin_pct", "operating_profit_margin_pct", "return_on_equity_pct",
        "return_on_capital_employed_pct", "return_on_assets_pct", "debt_to_equity",
        "interest_coverage", "asset_turnover", "fcf_conversion_pct", "capex_intensity_pct",
        "composite_quality_score"
    ]
    
    # Build peer percentile lookup: (peer_group, metric, company_id, year) -> percentile_rank
    peer_pct = pd.read_sql("SELECT * FROM peer_percentiles", con)
    # For latest year per company in each group
    # Since peer_percentiles has multiple years, we need latest year for each company
    latest_year_per_company = fr.sort_values("year_int").groupby("company_id")["year"].last().to_dict()
    
    # Filter peer_pct to latest year for each company
    peer_pct["year_key"] = peer_pct.apply(lambda r: (r["company_id"], r["peer_group_name"], r["metric"], r["year"]), axis=1)
    # Create a dict for quick lookup
    pct_lookup = {}
    for _, r in peer_pct.iterrows():
        key = (r["peer_group_name"], r["company_id"], r["metric"], r["year"])
        pct_lookup[key] = r["percentile_rank"]
    
    # Also get benchmark companies
    benchmark_map = dict(zip(pg["company_id"], pg["is_benchmark"]))
    
    con.close()
    
    # Create Excel workbook
    wb = Workbook()
    
    # Remove default sheet
    if "Sheet" in wb.sheetnames:
        wb.remove(wb["Sheet"])
    
    for pg_name in sorted(peer_groups):
        # Get members of this peer group
        members = pg[pg["peer_group_name"] == pg_name]["company_id"].tolist()
        
        # Get latest year for each member (use their individual latest year)
        rows_data = []
        for cid in members:
            year = latest_year_per_company.get(cid, "2024")
            row = {
                "company_id": cid,
                "company_name": comp_name_map.get(cid, cid),
                "is_benchmark": benchmark_map.get(cid, 0),
            }
            # Add metric values from financial_ratios
            fr_row = latest_fr[latest_fr["company_id"] == cid]
            if not fr_row.empty:
                fr_row = fr_row.iloc[0]
                for m in metrics:
                    row[m] = fr_row.get(m)
            else:
                for m in metrics:
                    row[m] = None
            # Add percentile ranks
            for m in metrics:
                key = (pg_name, cid, m, year)
                row[f"{m}_pct"] = pct_lookup.get(key)
            rows_data.append(row)
        
        df_out = pd.DataFrame(rows_data)
        
        # Add summary row (peer group median)
        summary = {"company_id": "PEER_MEDIAN", "company_name": "Peer Group Median", "is_benchmark": 0}
        for m in metrics:
            vals = df_out[m].dropna()
            summary[m] = vals.median() if not vals.empty else None
            vals_pct = df_out[f"{m}_pct"].dropna()
            summary[f"{m}_pct"] = vals_pct.median() if not vals_pct.empty else None
        
        df_out = pd.concat([df_out, pd.DataFrame([summary])], ignore_index=True)
        
        # Sort by is_benchmark desc, then company_id (benchmark first)
        df_out = df_out.sort_values(["is_benchmark", "company_id"], ascending=[False, True]).reset_index(drop=True)
        
        # Write to sheet
        sheet_name = pg_name[:31]
        ws = wb.create_sheet(sheet_name)
        
        # Write headers
        headers = ["company_id", "company_name"] + \
                  [f"{m}" for m in metrics] + \
                  [f"{m}_pct" for m in metrics] + \
                  ["is_benchmark"]
        for col_idx, h in enumerate(headers, 1):
            ws.cell(row=1, column=col_idx, value=h)
            ws.cell(row=1, column=col_idx).font = Font(bold=True)
            ws.cell(row=1, column=col_idx).alignment = Alignment(horizontal="center", wrap_text=True)
        
        # Write data
        for row_idx, (_, row) in enumerate(df_out.iterrows(), 2):
            for col_idx, h in enumerate(headers, 1):
                val = row.get(h)
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.alignment = Alignment(horizontal="center")
                
                # Highlight benchmark row
                if row.get("is_benchmark") == 1:
                    cell.fill = GOLD_FILL
                
                # Color-code percentile rank columns (every other column after metric columns)
                if h.endswith("_pct") and val is not None and not pd.isna(val):
                    pct = float(val)
                    if pct >= 0.75:
                        cell.fill = GREEN_FILL
                    elif pct <= 0.25:
                        cell.fill = RED_FILL
                    else:
                        cell.fill = YELLOW_FILL
        
        # Auto-adjust column widths
        for col_idx in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = 18
    
    # Save
    output_path = OUTPUT_DIR / "peer_comparison.xlsx"
    wb.save(output_path)
    print(f"Generated {output_path} with {len(peer_groups)} sheets")
    return output_path

if __name__ == "__main__":
    generate_peer_comparison()