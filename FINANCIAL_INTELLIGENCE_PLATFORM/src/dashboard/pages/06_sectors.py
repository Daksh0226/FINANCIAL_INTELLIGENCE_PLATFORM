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
import pathlib, sqlite3
import plotly.express as px
import plotly.graph_objects as go

from src.dashboard.utils.db import get_companies, get_ratios, get_sectors, get_bubble_chart_data, validate_chart_dataset

st.set_page_config(page_title="Sector Analysis — Financial Intelligence Platform", layout="wide")
try:
    from src.dashboard.utils.theme import inject_kinetic_theme, kinetic_marquee, apply_plotly_theme, is_dark_mode, get_theme_colors
    inject_kinetic_theme()
except Exception:
    def is_dark_mode(): return False
    def get_theme_colors(is_dark=None):
        is_dark = is_dark if is_dark is not None else False
        return {
            "isDark": is_dark,
            "chartBackground": "#0B0F14" if is_dark else "#FFFFFF",
            "chartTextColor": "#F8FAFC" if is_dark else "#0F172A",
            "legendColor": "#E2E8F0" if is_dark else "#334155",
            "tooltipBackground": "#111827" if is_dark else "#FFFFFF",
            "tooltipText": "#F8FAFC" if is_dark else "#0F172A",
            "tooltipBorder": "#334155" if is_dark else "#CBD5E1",
            "segmentBorder": "#0B0F14" if is_dark else "#FFFFFF",
            "containerBackground": "#0B0F14" if is_dark else "#FFFFFF",
            "containerBorder": "#334155" if is_dark else "#CBD5E1",
        }
    def kinetic_marquee(*a, **kw): pass
    def apply_plotly_theme(fig, theme=None): return fig


def _bubble_is_dark() -> bool:
    """CURRENT app theme for the Bubble Chart — same rerun as sector/year change.

    Root-cause fix: st.context.theme.type is the live Streamlit System/Light/Dark
    value for THIS rerun. Old code used query_params (async home JS) + 
    st.get_option("theme.base") which is always the config.toml value ("light"),
    so Dark UI still built a white Plotly figure.
    """
    try:
        t = st.context.theme.type
        if t == "dark":
            return True
        if t == "light":
            return False
    except Exception:
        pass
    try:
        qp_theme = st.query_params.get("theme", None)
        if qp_theme == "dark":
            return True
        if qp_theme == "light":
            return False
    except Exception:
        pass
    try:
        return bool(is_dark_mode())
    except Exception:
        return False


# 1) CURRENT application theme (before widgets / figure — re-read is cheap and same-rerun)
isDark = _bubble_is_dark()

st.title("🏢 Sector Analysis")
try:
    kinetic_marquee(["SECTOR BUBBLE — REVENUE × ROE × MARKET CAP", "MEDIAN KPI BARS"], variant="muted", speed="normal")
except Exception:
    pass

# Year selector for bubble chart (year-aware, not latest)
year = st.sidebar.selectbox("Select Year", [2019, 2020, 2021, 2022, 2023, 2024], index=5, key="sector_year")
st.sidebar.caption("Bubble chart updates for selected year.")

# Use common year-aware bubble data function (one row per company/year, no Cartesian)
# This ensures: 1) year filter BEFORE joins, 2) no duplicate company/year, 3) correct ROE/revenue/market_cap per selected year
comps = get_companies()
# Get year-aware bubble data via common function (handles caching with year+sector)
# We need sector list first - get all sectors from companies
sectors_all = sorted(comps["broad_sector"].dropna().unique().tolist())
selected_sector = st.selectbox("Select sector", sectors_all, index=0) if sectors_all else None
if not selected_sector:
    st.warning("No sector data.")
    st.stop()

# Fetch year-aware bubble data for selected sector and year (validated, one row per company)
bubble_raw = get_bubble_chart_data(year, selected_sector)

# Internal validation (kept for logic, no UI)
validation = validate_chart_dataset(bubble_raw, year, selected_sector)

# Filter for bubble: need valid revenue, roe, market_cap
# Validation already ensures one row per company/year, no duplicates, correct year
plot_df = bubble_raw.copy()
# Ensure numeric and handle NaN - display N/A for missing, do not fabricate 0
plot_df["sales"] = pd.to_numeric(plot_df["revenue"], errors="coerce") if "revenue" in plot_df.columns else pd.to_numeric(plot_df["sales"], errors="coerce") if "sales" in plot_df.columns else np.nan
# ROE is already as percentage (15 means 15%), do not multiply by 100 again
plot_df["return_on_equity_pct"] = pd.to_numeric(plot_df["roe"], errors="coerce") if "roe" in plot_df.columns else pd.to_numeric(plot_df["return_on_equity_pct"], errors="coerce")
plot_df["market_cap_crore"] = pd.to_numeric(plot_df["market_cap"], errors="coerce") if "market_cap" in plot_df.columns else pd.to_numeric(plot_df["market_cap_crore"], errors="coerce")
# Keep original for display
plot_df["sales_display"] = plot_df["sales"]
plot_df["roe_display"] = plot_df["return_on_equity_pct"]
# For bubble size, use actual market cap, clip minimal
plot_df["mc_size"] = plot_df["market_cap_crore"].fillna(500)
plot_df["mc_size"] = plot_df["mc_size"].clip(lower=500)
# For bubble, filter to valid sales and ROE (revenue and ROE must be numeric, market cap can be minimal)
plot_df_bubble = plot_df.dropna(subset=["sales", "return_on_equity_pct"])
if plot_df_bubble.empty:
    st.warning(f"No valid sales/ROE data for {selected_sector} in {year} - showing N/A")
    plot_df_bubble = plot_df

# For sector median KPI bar chart below, also use year-aware data
# Compute medians for selected sector for selected year (not latest)
latest = plot_df  # year-aware, already filtered to selected sector and year
show_all = st.checkbox("Show all sectors (uncheck to focus on selected sector only)", value=False)
if show_all:
    # For show_all, get all sectors for selected year
    all_bubble = get_bubble_chart_data(year, None)
    # Validate
    plot_df = all_bubble.copy()
    plot_df["sales"] = pd.to_numeric(plot_df["revenue"], errors="coerce") if "revenue" in plot_df.columns else pd.to_numeric(plot_df["sales"], errors="coerce")
    plot_df["return_on_equity_pct"] = pd.to_numeric(plot_df["roe"], errors="coerce") if "roe" in plot_df.columns else pd.to_numeric(plot_df["return_on_equity_pct"], errors="coerce")
    plot_df["market_cap_crore"] = pd.to_numeric(plot_df["market_cap"], errors="coerce") if "market_cap" in plot_df.columns else pd.to_numeric(plot_df["market_cap_crore"], errors="coerce")
    plot_df["mc_size"] = plot_df["market_cap_crore"].fillna(500).clip(lower=500)
    plot_df_bubble = plot_df.dropna(subset=["sales", "return_on_equity_pct"])
    if plot_df_bubble.empty:
        st.warning(f"No valid data for {year}")
        plot_df_bubble = plot_df
else:
    # Already have plot_df for selected sector
    pass

# Re-read CURRENT theme immediately before figure creation (after ALL widgets).
# Sector/year/show_all reruns re-execute this line — no stale light figure.
isDark = _bubble_is_dark()
if isDark:
    chartBackground = "#09090B"
    textColor = "#F9FAFB"
    gridColor = "#3F4650"
    axisColor = "#59616D"
else:
    chartBackground = "#FFFFFF"
    textColor = "#111827"
    gridColor = "#D1D5DB"
    axisColor = "#9CA3AF"
chartTextColor = textColor
legendColor = textColor
tickColor = textColor
try:
    _tc = get_theme_colors(isDark)
    tooltipBackground = _tc["tooltipBackground"]
    tooltipText = _tc["tooltipText"]
    tooltipBorder = _tc["tooltipBorder"]
except Exception:
    tooltipBackground = "#111827" if isDark else "#FFFFFF"
    tooltipText = "#F9FAFB" if isDark else "#111827"
    tooltipBorder = "#334155" if isDark else "#D1D5DB"

fig = px.scatter(
    plot_df_bubble,
    x="sales",
    y="return_on_equity_pct",
    size="mc_size",
    color="sub_sector",
    hover_name="company_name",
    hover_data={"company_id": True, "sales": ":.0f", "return_on_equity_pct": ":.1f", "market_cap_crore": ":.0f", "sub_sector": True, "mc_size": False},
    title=f"Bubble — {selected_sector if not show_all else 'All Sectors'} : X=Revenue (₹ Cr), Y=ROE %, Size=Market Cap, Colour=Sub-sector",
    labels={"sales": "Revenue (₹ Cr)", "return_on_equity_pct": "ROE %", "sub_sector": "Sub-sector", "mc_size": "Market Cap (Cr)"},
    size_max=55,
    opacity=0.78,
)
fig.update_layout(height=520, margin=dict(l=20, r=20, t=60, b=20), legend=dict(orientation="h", y=-0.18))
fig.update_traces(marker=dict(line=dict(width=1, color="DarkSlateGrey")))
fig = apply_plotly_theme(fig)
# FINAL theme for THIS figure — current isDark only, after apply_plotly_theme.
# Bubble Chart ONLY: fig2 / other pages untouched.
fig.update_layout(
    paper_bgcolor=chartBackground,
    plot_bgcolor=chartBackground,
    font=dict(color=textColor, family="Inter, sans-serif"),
    title=dict(font=dict(color=textColor, family="Space Grotesk, Inter, sans-serif")),
    legend=dict(
        orientation="h", y=-0.18, x=0.5, xanchor="center",
        font=dict(color=textColor, family="Inter, sans-serif", size=10),
        title_font=dict(color=textColor, family="Inter, sans-serif", size=10),
    ),
    xaxis=dict(
        title=dict(text="Revenue (₹ Cr)", font=dict(color=textColor, family="Inter, sans-serif")),
        tickfont=dict(color=textColor, family="Inter, sans-serif"),
        showgrid=True, gridcolor=gridColor, gridwidth=1, layer="above traces",
        showline=True, linecolor=axisColor, linewidth=1,
        zeroline=True, zerolinecolor=axisColor,
    ),
    yaxis=dict(
        title=dict(text="ROE %", font=dict(color=textColor, family="Inter, sans-serif")),
        tickfont=dict(color=textColor, family="Inter, sans-serif"),
        showgrid=True, gridcolor=gridColor, gridwidth=1, layer="above traces",
        showline=True, linecolor=axisColor, linewidth=1,
        zeroline=True, zerolinecolor=axisColor,
    ),
    hoverlabel=dict(bgcolor=tooltipBackground, font=dict(color=tooltipText, family="Inter, sans-serif", size=12), bordercolor=tooltipBorder),
    height=520,
    margin=dict(l=20, r=20, t=60, b=20),
)
# Explicit per-axis final pass (grid + text) — still bubble-only
fig.update_xaxes(
    showgrid=True, gridwidth=1, gridcolor=gridColor, layer="above traces",
    showline=True, linecolor=axisColor, linewidth=1,
    zeroline=True, zerolinecolor=axisColor,
    title_font=dict(color=textColor, family="Inter, sans-serif"),
    tickfont=dict(color=textColor, family="Inter, sans-serif"),
)
fig.update_yaxes(
    showgrid=True, gridwidth=1, gridcolor=gridColor, layer="above traces",
    showline=True, linecolor=axisColor, linewidth=1,
    zeroline=True, zerolinecolor=axisColor,
    title_font=dict(color=textColor, family="Inter, sans-serif"),
    tickfont=dict(color=textColor, family="Inter, sans-serif"),
)
# Horizontal divider/header line matching first screenshot - theme-aware, full width, immediately above bubble chart
st.markdown('<div style="border-top: 2px solid var(--app-border); margin: 24px 0 16px 0; width: 100%;"></div>', unsafe_allow_html=True)
# Key includes theme+sector+year so Streamlit remounts a fresh chart on any of those changes
bubble_key = f"sector_bubble_{selected_sector}_{year}_{show_all}_{int(isDark)}"
st.plotly_chart(fig, use_container_width=True, key=bubble_key)
st.caption("Bubble chart: X=Revenue, Y=ROE, bubble size=Market Cap, colour=sub-sector. Uses Plotly scatter with size_max=55; constrained to page width.")

# Sector median KPI bar chart below bubble - YEAR-AWARE (selected year, not latest)
st.markdown("### Sector Median KPIs")
# Use year-aware ratios for selected year (not latest)
try:
    ratios_year = get_ratios(year=year)
    # Merge with companies to get broad_sector
    ratios_year = ratios_year.merge(comps[["company_id","broad_sector"]], on="company_id", how="left")
    median_metrics = ["return_on_equity_pct","return_on_capital_employed_pct","net_profit_margin_pct","debt_to_equity","revenue_cagr_5yr"]
    median_metrics = [m for m in median_metrics if m in ratios_year.columns]
    sector_medians = ratios_year.groupby("broad_sector")[median_metrics].median(numeric_only=True).reset_index()
except Exception:
    # Fallback to bubble data if ratios not available
    median_metrics = ["return_on_equity_pct","return_on_capital_employed_pct","net_profit_margin_pct","debt_to_equity","revenue_cagr_5yr"]
    # Try to get from bubble all data
    try:
        all_for_median = get_bubble_chart_data(year, None)
        # Need to join with ratios for additional metrics, fallback
        sector_medians = pd.DataFrame()
    except:
        sector_medians = pd.DataFrame()

# For selected sector: show bar chart of its medians
sel_meds = sector_medians[sector_medians["broad_sector"] == selected_sector]
if not sel_meds.empty:
    # Melt for bar chart
    melted = sel_meds.melt(id_vars=["broad_sector"], var_name="metric", value_name="median")
    # Friendly names
    friendly = {"return_on_equity_pct": "ROE %", "return_on_capital_employed_pct": "ROCE %", "net_profit_margin_pct": "NPM %", "debt_to_equity": "D/E", "revenue_cagr_5yr": "Rev CAGR 5Y %"}
    melted["metric_label"] = melted["metric"].map(friendly).fillna(melted["metric"])
    fig2 = px.bar(
        melted,
        x="metric_label",
        y="median",
        color="metric_label",
        title=f"Median KPIs — {selected_sector} (n={len(plot_df) if not show_all else len(latest[latest['broad_sector']==selected_sector])} companies)",
        text_auto=".2f",
    )
    fig2.update_layout(height=420, margin=dict(l=20, r=20, t=50, b=20), showlegend=False)
    fig2 = apply_plotly_theme(fig2)
    # Chart-local grid AFTER shared theme — Median KPIs only (horizontal Y grid; leave categorical X grid off)
    fig2.update_yaxes(showgrid=True, gridcolor=gridColor, gridwidth=1, showline=True, linecolor=axisColor, linewidth=1, zeroline=True, zerolinecolor=axisColor)
    st.plotly_chart(fig2, use_container_width=True)

# Full sector median table (computed) and canonical sectors table medians
st.markdown("**All Sectors — Median KPIs (computed from latest ratios)**")
st.dataframe(sector_medians.style.format(na_rep="N/A", precision=2), use_container_width=True, hide_index=True)
# Show canonical sectors table with calculated median_roe/median_pe/median_de (deterministic)
try:
    sectors_canonical = get_sectors()
    if not sectors_canonical.empty:
        st.markdown("**Canonical Sectors Table (median_roe/median_pe/median_de - calculated)**")
        st.dataframe(sectors_canonical.style.format(na_rep="N/A", precision=2), use_container_width=True, hide_index=True)
        st.caption("Medians are calculated deterministically: median_roe from latest ROE, median_pe from latest P/E, median_de from latest D/E. N/A indicates genuinely missing underlying values.")
except Exception:
    pass
