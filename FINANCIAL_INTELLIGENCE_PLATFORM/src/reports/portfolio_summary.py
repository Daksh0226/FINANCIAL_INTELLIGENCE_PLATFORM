"""Portfolio summary PDF: one page per company alphabetical by ticker, 6 KPIs + trend arrows"""
import pathlib, sqlite3
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER

DB_PATH = pathlib.Path("data/nifty100.db")
OUTPUT_DIR = pathlib.Path("reports/portfolio")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
NAVY = colors.HexColor("#0f2a44")

def generate():
    con = sqlite3.connect(str(DB_PATH))
    companies = pd.read_sql("SELECT company_id, company_name, broad_sector FROM companies ORDER BY company_id", con)
    fr = pd.read_sql("SELECT * FROM financial_ratios ORDER BY company_id, year", con)
    con.close()
    fr["year_int"] = pd.to_numeric(fr["year"], errors="coerce")
    # for trend arrows: compare latest vs previous year for each KPI
    kpis = ["return_on_equity_pct","return_on_capital_employed_pct","net_profit_margin_pct","debt_to_equity","revenue_cagr_5yr","free_cash_flow_cr"]
    kpi_labels = ["ROE %","ROCE %","NPM %","D/E","Rev CAGR 5Y %","FCF Cr"]

    doc = SimpleDocTemplate(str(OUTPUT_DIR / "portfolio_summary.pdf"), pagesize=A4, topMargin=10*mm, bottomMargin=10*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleNavy", parent=styles["Heading1"], textColor=colors.white, alignment=TA_CENTER, fontSize=14)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=NAVY, fontSize=11)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=7, leading=8)
    small_center = ParagraphStyle("small_center", parent=small, alignment=TA_CENTER)

    story = []
    for _, comp in companies.iterrows():
        cid = comp["company_id"]
        # header
        hdr = [[Paragraph(f"<b>{comp['company_name']} ({cid})</b> — {comp['broad_sector']}", title_style)]]
        tbl = Table(hdr, colWidths=[190*mm])
        tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1), NAVY), ("TOPPADDING",(0,0),(-1,-1),6), ("BOTTOMPADDING",(0,0),(-1,-1),6)]))
        story.append(tbl)
        story.append(Spacer(1,4*mm))
        # latest and previous
        cdf = fr[fr["company_id"]==cid].sort_values("year_int")
        if cdf.empty:
            story.append(Paragraph("No data available", small))
            story.append(PageBreak())
            continue
        latest = cdf.iloc[-1]
        prev = cdf.iloc[-2] if len(cdf)>=2 else latest
        # build KPI table with trend arrows
        header = [Paragraph(f"<b>{lbl}</b>", small_center) for lbl in ["KPI","Latest","Prev","Trend"]]
        data = [header]
        for kpi, lbl in zip(kpis, kpi_labels):
            latest_val = latest.get(kpi)
            prev_val = prev.get(kpi)
            # format
            def fmt(v):
                if pd.isna(v):
                    return "N/A"
                if "D/E" in lbl:
                    return f"{v:.2f}"
                elif "FCF" in lbl:
                    return f"{v:.0f}"
                else:
                    return f"{v:.1f}"
            # trend arrow logic: up if improved >2%, down if declined >2%, else right
            # For D/E lower is better so invert logic
            arrow = "→"
            if pd.notna(latest_val) and pd.notna(prev_val) and prev_val !=0:
                pct_change = (latest_val - prev_val) / abs(prev_val) * 100 if prev_val !=0 else 0
                # for D/E, improvement is decrease
                if "D/E" in lbl:
                    if pct_change < -2:
                        arrow = "↑"  # D/E down is good -> up arrow?
                        # Use up arrow for improvement
                    elif pct_change > 2:
                        arrow = "↓"
                    else:
                        arrow = "→"
                else:
                    if pct_change > 2:
                        arrow = "↑"
                    elif pct_change < -2:
                        arrow = "↓"
                    else:
                        arrow = "→"
            else:
                arrow = "→"
            data.append([
                Paragraph(f"<font size=7>{lbl}</font>", small_center),
                Paragraph(f"<font size=7>{fmt(latest_val)}</font>", small_center),
                Paragraph(f"<font size=7>{fmt(prev_val)}</font>", small_center),
                Paragraph(f"<font size=9>{arrow}</font>", small_center),
            ])
        t = Table(data, colWidths=[50*mm,45*mm,45*mm,40*mm])
        t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.5, colors.grey), ("BACKGROUND",(0,0),(-1,0), colors.lightgrey), ("ALIGN",(0,0),(-1,-1),"CENTER"), ("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
        story.append(t)
        story.append(Spacer(1,4*mm))
        story.append(Paragraph(f"Ticker {cid} — Latest year {latest.get('year')} vs {prev.get('year')}. Trend arrows: ↑ improved, ↓ declined, → flat within 2%.", small))
        story.append(Spacer(1,6*mm))
        story.append(Paragraph(f"Sector {comp['broad_sector']} | Data as of FY2024 | Financial Intelligence Platform", small_center))
        story.append(PageBreak())

    # Remove last PageBreak extra
    if story and isinstance(story[-1], PageBreak):
        story = story[:-1]
    doc.build(story)
    print(f"Generated portfolio_summary.pdf with {len(companies)} companies")
    # verify pages
    import fitz
    doc2 = fitz.open(str(OUTPUT_DIR / "portfolio_summary.pdf"))
    print(f"Pages: {len(doc2)} size: {(OUTPUT_DIR / 'portfolio_summary.pdf').stat().st_size}")

if __name__ == "__main__":
    generate()
