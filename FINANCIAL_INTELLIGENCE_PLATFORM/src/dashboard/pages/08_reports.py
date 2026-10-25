import sys, pathlib
try:
    _root = pathlib.Path(__file__).resolve().parents[2]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    _root2 = pathlib.Path.cwd()
    if str(_root2) not in sys.path:
        sys.path.insert(0, str(_root2))
except: pass
import streamlit as st
import pathlib, sqlite3
import pandas as pd

st.set_page_config(page_title="Annual Reports — Financial Intelligence Platform", layout="wide")
try:
    from src.dashboard.utils.theme import inject_kinetic_theme, kinetic_marquee
    inject_kinetic_theme()
except Exception:
    pass
st.title("📄 Annual Reports")
try:
    kinetic_marquee(["ANNUAL REPORTS — BSE PDF LINKS — 404 BADGE", "92 TEARSHEETS"], variant="muted", speed="normal")
except Exception:
    pass

DB_PATH = pathlib.Path("data/nifty100.db")
if not DB_PATH.exists():
    DB_PATH = pathlib.Path(__file__).resolve().parents[1] / "data" / "nifty100.db"

con = sqlite3.connect(str(DB_PATH))
docs = pd.read_sql("SELECT * FROM documents", con)
comps = pd.read_sql("SELECT company_id, company_name, broad_sector FROM companies", con)
con.close()

# Company search box
labels = {r["company_id"]: f"{r['company_id']} — {r['company_name']}" for _, r in comps.iterrows()}
cid = st.selectbox("Search company", comps["company_id"].tolist(), format_func=lambda x: labels.get(x, x))

st.markdown(f"### BSE Annual Reports — {cid} ({labels.get(cid, cid)})")
rows = docs[docs["company_id"] == cid].sort_values("year", ascending=False)

# Optional URL health check (HEAD request) — graceful fallback if network unavailable
def check_url_available(url: str) -> bool | None:
    """Return True if URL returns 200, False if 404/error, None if cannot check (offline/timeout)."""
    if not url or not str(url).startswith("http"):
        return False
    try:
        import httpx
        # Short timeout; not all URLs will be reachable in CI/offline
        r = httpx.head(url, timeout=3.0, follow_redirects=True)
        if r.status_code == 200:
            return True
        if r.status_code == 404:
            return False
        # For other codes, try GET fallback quickly
        if r.status_code >= 400:
            return False
        return True
    except Exception:
        return None  # unknown — don't flag as unavailable when offline

if rows.empty:
    st.info(f"No annual report entries for {cid}.")
else:
    st.caption(f"{len(rows)} report years available — clickable BSE PDF links below. If a URL returns 404, a red **Report unavailable** badge is shown.")
    for _, r in rows.iterrows():
        url = str(r["report_url"]) if pd.notna(r["report_url"]) else ""
        year = r["year"]
        availability = check_url_available(url) if url else False
        if availability is False:
            st.markdown(
                f"- **{year}**: <span style='background:#fce8e6;color:#a50e0e;padding:2px 8px;border-radius:999px;font-size:0.85em;'>Report unavailable</span> — URL returned 404: `{url}`",
                unsafe_allow_html=True,
            )
        elif availability is None:
            # Cannot verify (offline) — show link without badge but note
            if url:
                st.markdown(f"- **{year}**: [📄 {url}]({url}) <span style='color:#666;font-size:0.85em;'>(availability not checked — offline)</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"- **{year}**: <span style='background:#fce8e6;color:#a50e0e;padding:2px 8px;border-radius:999px;'>Report unavailable</span> — no URL stored", unsafe_allow_html=True)
        else:
            st.markdown(f"- **{year}**: [📄 {url}]({url})")

# Tearsheet PDFs
st.markdown("---")
st.subheader("Tearsheet PDFs")
pdf_path = pathlib.Path(f"reports/tearsheets/{cid}_tearsheet.pdf")
if not pdf_path.exists():
    pdf_path = pathlib.Path(__file__).resolve().parents[1] / "reports" / "tearsheets" / f"{cid}_tearsheet.pdf"
if pdf_path.exists():
    with open(pdf_path, "rb") as f:
        st.download_button(f"⬇️ Download {cid} Tearsheet PDF", f, file_name=f"{cid}_tearsheet.pdf", mime="application/pdf")
else:
    st.caption(f"Tearsheet not yet generated for {cid} — run `python -m src.reports.tearsheet` or `make report` to generate.")

# Sector reports discovery
sector_dir = pathlib.Path("reports/sector")
if not sector_dir.exists():
    sector_dir = pathlib.Path(__file__).resolve().parents[1] / "reports" / "sector"
if sector_dir.exists() and sector_dir.is_dir():
    files = sorted(sector_dir.glob("*.pdf"))
    if files:
        st.subheader("Sector Reports")
        for p in files[:15]:
            st.markdown(f"- {p.name}")
        if len(files) > 15:
            st.caption(f"Showing 15 of {len(files)} sector reports.")
    else:
        st.caption("No sector report PDFs found in reports/sector/.")
else:
    st.caption("Sector reports folder not found — expected at `reports/sector/`.")