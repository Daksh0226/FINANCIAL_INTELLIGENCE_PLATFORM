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
import plotly.graph_objects as go

from src.dashboard.utils.db import get_companies, get_ratios

st.set_page_config(page_title="Trend Analysis — Financial Intelligence Platform", layout="wide")
try:
    from src.dashboard.utils.theme import inject_kinetic_theme, kinetic_marquee, apply_plotly_theme
    inject_kinetic_theme()
except Exception:
    pass
st.title("📈 Trend Analysis")
try:
    kinetic_marquee(["TREND ANALYSIS — 3 METRICS OVERLAY — YoY ANNOTATIONS", "10-YEAR MOMENTUM"], variant="muted", speed="normal")
except Exception:
    pass

comps = get_companies()
ratios = get_ratios().copy()
ratios["year_int"] = pd.to_numeric(ratios["year"], errors="coerce")

st.markdown("Select a company and overlay up to **3 metrics** — 10-year line chart with **YoY % change annotation** on each point.")

# Company search
labels = {r["company_id"]: f"{r['company_id']} — {r['company_name']}" for _, r in comps.iterrows()}
ticker = st.selectbox("Company", comps["company_id"].tolist(), format_func=lambda x: labels.get(x, x))

# Metric selector — multi, up to 3
AVAILABLE_METRICS = [
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "debt_to_equity",
    "interest_coverage",
    "free_cash_flow_cr",
    "return_on_assets_pct",
    "asset_turnover",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "composite_quality_score",
]
# Friendly names
FRIENDLY = {
    "return_on_equity_pct": "ROE %",
    "return_on_capital_employed_pct": "ROCE %",
    "net_profit_margin_pct": "NPM %",
    "operating_profit_margin_pct": "OPM %",
    "debt_to_equity": "D/E",
    "interest_coverage": "ICR",
    "free_cash_flow_cr": "FCF (₹ Cr)",
    "return_on_assets_pct": "ROA %",
    "asset_turnover": "Asset Turnover",
    "revenue_cagr_5yr": "Rev CAGR 5Y %",
    "pat_cagr_5yr": "PAT CAGR 5Y %",
    "composite_quality_score": "Quality Score",
}

selected_metrics = st.multiselect(
    "Select up to 3 metrics to overlay",
    AVAILABLE_METRICS,
    default=AVAILABLE_METRICS[:2],
    format_func=lambda x: FRIENDLY.get(x, x),
    max_selections=3,
    help="Pick 1-3 metrics; chart overlays them with separate y-axes if scales differ.",
)

if not selected_metrics:
    st.info("Select 1-3 metrics to display the trend.")
    st.stop()

df = ratios[ratios["company_id"] == ticker].copy()
if df.empty:
    st.warning(f"No data for {ticker}.")
    st.stop()
df = df.sort_values("year_int").tail(10)
if len(df) < 3:
    st.caption("ℹ️ Less than 10 years available — showing available history only.")
    if len(df) == 0:
        st.warning("No history to plot.")
        st.stop()

# Build figure — up to 3 metrics, use secondary y if needed (scale-aware)
fig = go.Figure()
colors = ["#4C78A8", "#F58518", "#54A24B"]
# Decide axis assignment: first metric on y, second on y2, third on y (or separate)
for idx, metric in enumerate(selected_metrics):
    y = df[metric]
    # YoY % change
    yoy = y.pct_change() * 100
    # Text annotations: show YoY on each point
    text_labels = []
    for i in range(len(df)):
        val = y.iloc[i]
        ch = yoy.iloc[i]
        if pd.isna(val):
            text_labels.append("N/A")
        elif pd.isna(ch) or i == 0:
            # first point no YoY
            if pd.notna(val):
                text_labels.append(f"{val:.1f}" if metric != "free_cash_flow_cr" else f"{val:,.0f}")
            else:
                text_labels.append("N/A")
        else:
            arrow = "▲" if ch > 0 else "▼" if ch < 0 else "—"
            if metric in ["debt_to_equity", "free_cash_flow_cr"]:
                text_labels.append(f"{val:.2f} ({arrow} {ch:+.1f}%)" if pd.notna(val) else "N/A")
            else:
                text_labels.append(f"{val:.1f} ({arrow} {ch:+.1f}%)" if pd.notna(val) else "N/A")
    yaxis = "y" if idx == 0 else ("y2" if idx == 1 else "y3")
    fig.add_trace(go.Scatter(
        x=df["year"],
        y=y,
        name=FRIENDLY.get(metric, metric),
        mode="lines+markers+text",
        text=text_labels,
        textposition="top center",
        textfont=dict(size=9),
        line=dict(color=colors[idx % len(colors)], width=3),
        marker=dict(size=8, color=colors[idx % len(colors)]),
        yaxis=yaxis,
        hovertemplate=f"{FRIENDLY.get(metric, metric)}: %{{y}}<br>YoY: %{{text}}<extra>{metric}</extra>",
    ))

# Layout: up to 3 y-axes if 3 metrics
layout_kwargs = dict(
    title=f"{ticker} — 10-Year Trend Overlay ({', '.join([FRIENDLY.get(m,m) for m in selected_metrics])})",
    xaxis=dict(title="Year", showgrid=True),
    yaxis=dict(title=FRIENDLY.get(selected_metrics[0], selected_metrics[0]), side="left", showgrid=True),
    height=520,
    margin=dict(l=20, r=20, t=60, b=20),
    legend=dict(orientation="h", y=1.08),
    hovermode="x unified",
)
if len(selected_metrics) >= 2:
    layout_kwargs["yaxis2"] = dict(title=FRIENDLY.get(selected_metrics[1], selected_metrics[1]), overlaying="y", side="right", showgrid=False)
if len(selected_metrics) == 3:
    layout_kwargs["yaxis3"] = dict(title=FRIENDLY.get(selected_metrics[2], selected_metrics[2]), overlaying="y", side="right", position=0.95, showgrid=False)

fig.update_layout(**layout_kwargs)
# Constrain width via use_container_width in streamlit
st.plotly_chart(fig, use_container_width=True)
st.caption("YoY % change is annotated above each data point (▲ up / ▼ down). Gaps indicate missing data (N/A). Chart does not overflow page width (use_container_width).")

# Also show data table with YoY
st.markdown("#### Data Table (with YoY %)")
tbl = df[["year"] + selected_metrics].copy()
for m in selected_metrics:
    tbl[m + " YoY %"] = tbl[m].pct_change()*100
st.dataframe(tbl.style.format(na_rep="N/A", precision=2), use_container_width=True, hide_index=True)