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
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from src.dashboard.utils.db import get_companies, get_ratios, get_pl, get_bs, get_cf

st.set_page_config(page_title="Company Profile — Financial Intelligence Platform", layout="wide")
try:
    from src.dashboard.utils.theme import inject_kinetic_theme, kinetic_marquee, apply_plotly_theme
    inject_kinetic_theme()
except Exception:
    def apply_plotly_theme(fig, theme=None): return fig

def _target_grid_colors():
    """Live theme for chart-local gridlines only (not global theme)."""
    try:
        t = st.context.theme.type
        if t == "dark":
            return "#3F4650", "#59616D"
        if t == "light":
            return "#D1D5DB", "#9CA3AF"
    except Exception:
        pass
    try:
        qp = st.query_params.get("theme")
        if qp == "dark":
            return "#3F4650", "#59616D"
        if qp == "light":
            return "#D1D5DB", "#9CA3AF"
    except Exception:
        pass
    return "#D1D5DB", "#9CA3AF"

GRID_COLOR, AXIS_COLOR = _target_grid_colors()

st.title("👤 Company Profile")
try:
    kinetic_marquee(["COMPANY PROFILE — 10-YEAR FINANCIALS", "ROE × ROCE — REVENUE × PROFIT"], variant="muted", speed="normal")
except Exception:
    pass

comps = get_companies()
ratios_all = get_ratios()
pl_all = get_pl()
bs_all = get_bs()
cf_all = get_cf()

# --- Search box with autocomplete (text + dropdown) ---
st.markdown("**Search company by name or ticker** — type to filter, then select from dropdown.")
# Text search for autocomplete
search_text = st.text_input("🔍 Type company name or ticker (e.g. RELIANCE, TCS, INFY)", value="", placeholder="Start typing…")
# Build options matching text
if search_text.strip():
    mask = comps["company_name"].str.contains(search_text, case=False, na=False) | comps["company_id"].str.contains(search_text, case=False, na=False) | comps["nse_ticker"].astype(str).str.contains(search_text, case=False, na=False)
    filtered = comps[mask]
    if filtered.empty:
        st.error("Ticker not found — please try another")
        st.stop()
    options = filtered["company_id"].tolist()
    # show label with name
    labels = {r["company_id"]: f"{r['company_id']} — {r['company_name']}" for _, r in filtered.iterrows()}
    ticker = st.selectbox("Select from matches", options, format_func=lambda x: labels.get(x, x))
else:
    # Default: full dropdown
    labels_all = {r["company_id"]: f"{r['company_id']} — {r['company_name']}" for _, r in comps.iterrows()}
    ticker = st.selectbox("Select company", comps["company_id"].tolist(), format_func=lambda x: labels_all.get(x, x))

# Validate ticker
if ticker not in comps["company_id"].values:
    st.error("Ticker not found — please try another")
    st.stop()

comp = comps[comps["company_id"] == ticker].iloc[0]

# --- Company card ---
st.markdown("---")
col_card1, col_card2 = st.columns([2, 1])
with col_card1:
    st.subheader(f"{comp['company_name']}  —  {ticker}")
    st.markdown(
        f"**Sector:** {comp['broad_sector'] if pd.notna(comp['broad_sector']) else 'N/A'} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"**Sub-sector:** {comp['sub_sector'] if pd.notna(comp['sub_sector']) else 'N/A'} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"**NSE Ticker:** {comp['nse_ticker'] if pd.notna(comp['nse_ticker']) else ticker}"
    )
    about = comp.get("about", "")
    if pd.notna(about) and str(about).strip():
        st.write(str(about))
    else:
        st.caption("No description available.")
with col_card2:
    st.metric("Market Cap Category", comp.get("market_cap_category", "N/A") if pd.notna(comp.get("market_cap_category")) else "N/A")
    # Data availability note for partial data
    years_count = len(ratios_all[ratios_all["company_id"] == ticker])
    st.caption(f"📅 Data available: **{years_count} years** of ratios")
    if years_count < 10:
        st.info("ℹ️ Less than 10 years of data available — charts show available history only.")

# --- 6 KPI tiles (latest year) ---
st.markdown("### Key Metrics — Latest Year")
df_r = ratios_all[ratios_all["company_id"] == ticker].copy()
if not df_r.empty:
    df_r["year_int"] = pd.to_numeric(df_r["year"], errors="coerce")
    df_r = df_r.sort_values("year_int")
    latest = df_r.iloc[-1]
    latest_year = latest["year"]
    st.caption(f"Latest year: **{latest_year}**")
    def fmt(v, fmt_str="{:.1f}", suffix=""):
        if pd.isna(v):
            return "N/A"
        try:
            return fmt_str.format(float(v)) + suffix
        except Exception:
            return str(v) + suffix

    # --- Per-metric TTM -> latest annual fallback (same company only) ---
    # The latest row (TTM when present) can hold NULL for balance-sheet/cash-flow
    # derived metrics. Resolve each KPI independently so a missing TTM value falls
    # back to this company's own latest annual value instead of showing N/A. Only
    # NULL/NaN/non-numeric triggers the fallback, so 0 and negatives stay valid.
    def _num(v):
        if v is None:
            return None
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            return None
        n = pd.to_numeric(v, errors="coerce")
        return None if pd.isna(n) else float(n)

    annual_r = df_r[df_r["year_int"].notna()].sort_values("year_int")

    def pick(col):
        """Return (value, used_annual_fallback) for a single KPI column."""
        v = _num(latest.get(col))
        if v is not None:
            return v, False
        if col not in annual_r.columns:
            return None, False
        s = pd.to_numeric(annual_r[col], errors="coerce").dropna()
        if s.empty:
            return None, False
        return float(s.iloc[-1]), True

    roe, roe_fb = pick("return_on_equity_pct")
    roce, roce_fb = pick("return_on_capital_employed_pct")
    npm, npm_fb = pick("net_profit_margin_pct")
    de, de_fb = pick("debt_to_equity")
    cagr, cagr_fb = pick("revenue_cagr_5yr")
    fcf, fcf_fb = pick("free_cash_flow_cr")
    if any([roe_fb, roce_fb, npm_fb, de_fb, cagr_fb, fcf_fb]):
        st.caption("TTM; annual fallback used where TTM data is unavailable.")

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric("ROE", fmt(roe, "{:.1f}", "%"))
    with c2:
        st.metric("ROCE", fmt(roce, "{:.1f}", "%"))
    with c3:
        st.metric("Net Profit Margin", fmt(npm, "{:.1f}", "%"))
    with c4:
        st.metric("D/E", "N/A" if pd.isna(de) else f"{float(de):.2f}")
    with c5:
        st.metric("Revenue CAGR 5Y", fmt(cagr, "{:.1f}", "%"))
    with c6:
        st.metric("FCF (₹ Cr)", "N/A" if pd.isna(fcf) else f"{float(fcf):,.0f}")
else:
    st.warning("No ratio data for this ticker.")
    latest = None

# --- 10-year bar chart: Revenue and Net Profit ---
st.markdown("### Revenue & Net Profit — 10-Year Trend")
g = pl_all[pl_all["company_id"] == ticker].copy()
if not g.empty:
    g["year_int"] = pd.to_numeric(g["year"], errors="coerce")
    g = g.sort_values("year_int").tail(10)
    # Plotly bar with two metrics grouped
    fig = go.Figure()
    fig.add_trace(go.Bar(x=g["year"], y=g["sales"], name="Revenue (Sales)", marker_color="#4C78A8", hovertemplate="Revenue: %{y:,.0f} Cr<extra></extra>"))
    fig.add_trace(go.Bar(x=g["year"], y=g["net_profit"], name="Net Profit", marker_color="#F58518", hovertemplate="PAT: %{y:,.0f} Cr<extra></extra>"))
    fig.update_layout(
        barmode="group",
        title=f"Revenue and Net Profit (₹ Cr) — {ticker}",
        xaxis_title="Year",
        yaxis_title="₹ Crore",
        height=420,
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h", y=1.05),
        bargap=0.2,
    )
    fig = apply_plotly_theme(fig)
    # Chart-local grid override AFTER shared theme — Revenue + Net Profit only
    fig.update_xaxes(showgrid=True, gridcolor=GRID_COLOR, gridwidth=1, showline=True, linecolor=AXIS_COLOR, linewidth=1, zeroline=True, zerolinecolor=AXIS_COLOR)
    fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, gridwidth=1, showline=True, linecolor=AXIS_COLOR, linewidth=1, zeroline=True, zerolinecolor=AXIS_COLOR)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No P&L data available for revenue/profit chart.")

# --- ROE and ROCE dual-axis line chart over 10 years ---
st.markdown("### ROE & ROCE — Dual-Axis (10 Years)")
if not df_r.empty:
    df10 = df_r.sort_values("year_int").tail(10)
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=df10["year"], y=df10["return_on_equity_pct"], name="ROE %", mode="lines+markers", line=dict(color="#54A24B", width=3), yaxis="y"))
    fig2.add_trace(go.Scatter(x=df10["year"], y=df10["return_on_capital_employed_pct"], name="ROCE %", mode="lines+markers", line=dict(color="#E45756", width=3, dash="dash"), yaxis="y2"))
    fig2.update_layout(
        title=f"ROE vs ROCE — {ticker}",
        xaxis=dict(title="Year"),
        yaxis=dict(title="ROE %", side="left", showgrid=True),
        yaxis2=dict(title="ROCE %", side="right", overlaying="y", showgrid=False),
        height=420,
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h", y=1.05),
        hovermode="x unified",
    )
    fig2 = apply_plotly_theme(fig2)
    # Chart-local grid override AFTER shared theme — dual-axis primary grid only
    fig2.update_xaxes(showgrid=True, gridcolor=GRID_COLOR, gridwidth=1, showline=True, linecolor=AXIS_COLOR, linewidth=1, zeroline=True, zerolinecolor=AXIS_COLOR)
    fig2.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, gridwidth=1, showline=True, linecolor=AXIS_COLOR, linewidth=1, zeroline=True, zerolinecolor=AXIS_COLOR)
    fig2.update_layout(yaxis2=dict(showgrid=False, overlaying="y", side="right"))
    st.plotly_chart(fig2, use_container_width=True)
    # Show N/A note for missing points
    if df10["return_on_equity_pct"].isna().any() or df10["return_on_capital_employed_pct"].isna().any():
        st.caption("Note: N/A values are omitted from the line; gaps indicate missing data.")
else:
    st.info("No ROE/ROCE history available.")

# --- Pros and cons as green check / red cross badges ---
st.markdown("### Pros & Cons")
import pathlib, sqlite3
DB_PATH = pathlib.Path("data/nifty100.db")
if not DB_PATH.exists():
    DB_PATH = pathlib.Path(__file__).resolve().parents[1] / "data" / "nifty100.db"
try:
    con = sqlite3.connect(str(DB_PATH))
    pcs = pd.read_sql("SELECT type, description FROM prosandcons WHERE company_id = ?", con, params=(ticker,))
    con.close()
except Exception:
    pcs = pd.DataFrame()

if not pcs.empty:
    pros = pcs[pcs["type"].str.lower() == "pro"]["description"].tolist()
    cons = pcs[pcs["type"].str.lower() == "con"]["description"].tolist()
    cpro, ccon = st.columns(2)
    with cpro:
        st.markdown("**✅ Pros**")
        if pros:
            for p in pros:
                st.markdown(f"<span style='background:#e6f4ea;color:#137333;padding:4px 10px;border-radius:999px;display:inline-block;margin:4px 6px 4px 0;'>✅ {p}</span>", unsafe_allow_html=True)
        else:
            st.caption("No pros listed.")
    with ccon:
        st.markdown("**❌ Cons**")
        if cons:
            for c in cons:
                st.markdown(f"<span style='background:#fce8e6;color:#a50e0e;padding:4px 10px;border-radius:999px;display:inline-block;margin:4px 6px 4px 0;'>❌ {c}</span>", unsafe_allow_html=True)
        else:
            st.caption("No cons listed.")
else:
    st.caption("No pros/cons data for this company.")