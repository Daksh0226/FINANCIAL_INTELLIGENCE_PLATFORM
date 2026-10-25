import sys, pathlib
try:
    _root = pathlib.Path(__file__).resolve().parents[2]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    _root2 = pathlib.Path.cwd()
    if str(_root2) not in sys.path:
        sys.path.insert(0, str(_root2))
except: pass
import pathlib as _pl2
import streamlit as st
from src.dashboard.utils.theme import inject_kinetic_theme, kinetic_marquee, kinetic_hero

st.set_page_config(
    page_title="Financial Intelligence Platform",
    layout="wide",
    page_icon="📊",
    initial_sidebar_state="expanded",
)
inject_kinetic_theme()

# Hero — clean branding
kinetic_marquee(["FINANCIAL INTELLIGENCE PLATFORM — 100 COMPANIES", "10 SECTORS", "2011—2024 FINANCIALS", "STREAMLIT × PLOTLY × FASTAPI", "LIVE SCREENING × PEER RADAR × VALUATION FLAGS", "92 TEARSHEETS"], variant="accent", speed="fast")
kinetic_hero("INDIA EQUITIES · EST. 2026", "FINANCIAL", "INTELLIGENCE PLATFORM", title_line2_accent=True, subtitle="100 companies · 10 sectors · 2011–2024 financials — 8-screen Streamlit dashboard for screening, peer comparison and valuation.")
st.caption("100 companies · 10 sectors · 2011–2024 financials · 8 screens · Financial Intelligence Platform · EST. 2026")

# Sidebar navigation — Theme removed per final spec (native Streamlit menu handles System/Light/Dark, Image 2)
st.sidebar.title("Navigation")
st.sidebar.caption("Financial Intelligence Platform — 8 screens")

PAGES = {
    "🏠 Home": "pages/01_home.py",
    "👤 Company Profile": "pages/02_profile.py",
    "🔍 Screener": "pages/03_screener.py",
    "🤝 Peer Comparison": "pages/04_peers.py",
    "📈 Trend Analysis": "pages/05_trends.py",
    "🏢 Sector Analysis": "pages/06_sectors.py",
    "🗺️ Capital Allocation Map": "pages/07_capital.py",
    "📄 Annual Reports": "pages/08_reports.py",
}

# Also support pages under src/dashboard/pages if project uses that layout
choice = st.sidebar.radio("Go to", list(PAGES.keys()), index=0)
st.sidebar.markdown("---")
st.sidebar.info("💡 Tip: Use the sidebar to navigate. All 8 screens support any of the 100 tickers.")
st.sidebar.markdown("Run: `streamlit run src/dashboard/app.py --server.port 8501`")

# Main content
st.markdown(f"### Welcome — {choice}")
st.markdown(
    "This dashboard covers **100 companies** across **10 sectors** with 10-year financials. "
    "Use the sidebar or the buttons below to open any screen. Every screen handles missing data gracefully "
    "(shows **N/A** instead of crashing) and charts are constrained to page width."
)

# Quick nav buttons (2 rows)
cols = st.columns(4)
for i, (label, path) in enumerate(list(PAGES.items())[:4]):
    with cols[i]:
        if st.button(label, use_container_width=True, key=f"btn_{i}"):
            try:
                st.switch_page(path)
            except Exception:
                st.info(f"Navigate to `{path}` via the pages sidebar (Streamlit multipage).")

cols2 = st.columns(4)
for i, (label, path) in enumerate(list(PAGES.items())[4:]):
    with cols2[i]:
        if st.button(label, use_container_width=True, key=f"btn2_{i}"):
            try:
                st.switch_page(path)
            except Exception:
                st.info(f"Navigate to `{path}` via the pages sidebar.")

st.markdown("---")
kinetic_marquee(["AVERAGE ROE 14.5% — MEDIAN P/E 24.3", "DEBT-FREE 18 COS", "REV CAGR 5Y 12.1% — PEER RADAR 11 GROUPS", "TREEMAP 8 PATTERNS — 92 TEARSHEETS READY", "API 27 ENDPOINTS — FK CHECK 0"], variant="muted", speed="normal")
st.markdown("**Screens at a glance:**")
st.markdown(
    """
| # | Screen | File | Purpose |
|---|--------|------|---------|
| 1 | Home | `pages/01_home.py` | KPI tiles, sector donut, top-5 quality |
| 2 | Company Profile | `pages/02_profile.py` | Search, 6 KPIs, 10-yr Revenue/Profit, ROE/ROCE, pros/cons |
| 3 | Screener | `pages/03_screener.py` | 10 sliders, 6 presets, live table, CSV export |
| 4 | Peer Comparison | `pages/04_peers.py` | Group dropdown, radar vs peer avg, KPI table |
| 5 | Trend Analysis | `pages/05_trends.py` | Search + up-to-3 metrics overlay, YoY annotations |
| 6 | Sector Analysis | `pages/06_sectors.py` | Bubble (Revenue vs ROE, size=Market Cap), median bars |
| 7 | Capital Allocation Map | `pages/07_capital.py` | Treemap by 8 patterns, click to list companies |
| 8 | Annual Reports | `pages/08_reports.py` | BSE PDF links per year, 404 badge |
"""
)

# Health check
import pathlib as _pl
db_path = _pl.Path("data/nifty100.db")
if not db_path.exists():
    db_path = _pl.Path(__file__).resolve().parents[2] / "data" / "nifty100.db"
if db_path.exists():
    st.success(f"✅ Database found: `{db_path}`")
else:
    st.error(f"❌ Database not found at `{db_path}` — ETL must be run first (`make load`).")

# Provide fallback navigation hint for older Streamlit
try:
    st.page_link(PAGES[choice], label=f"Open {choice} →", icon="➡️")
except Exception:
    pass
