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
import streamlit.components.v1 as components

from src.dashboard.utils.db import get_companies, get_ratios, get_sectors, get_sector_breakdown_by_year

st.set_page_config(page_title="Home — Financial Intelligence Platform", layout="wide")
try:
    from src.dashboard.utils.theme import inject_kinetic_theme, kinetic_marquee, apply_plotly_theme, is_dark_mode, get_theme_colors
    inject_kinetic_theme()
except Exception:
    # fallback if theme utils not available
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

# --- Theme-aware helper: detect isDark via existing theme system ---
# Use query_params set by JS for System theme, fallback to is_dark_mode()
try:
    _qp = st.query_params
    _qp_theme = _qp.get("theme", None)
    if _qp_theme == "dark":
        isDark = True
    elif _qp_theme == "light":
        isDark = False
    else:
        isDark = is_dark_mode()
except Exception:
    isDark = is_dark_mode()

colors = get_theme_colors(isDark)
chartBackground = colors["chartBackground"]  # #0B0F14 dark, #FFFFFF light
chartTextColor = colors["chartTextColor"]  # #F8FAFC dark, #0F172A light
legendColor = colors["legendColor"]  # #E2E8F0 dark, #334155 light
tooltipBackground = colors["tooltipBackground"]
tooltipText = colors["tooltipText"]
tooltipBorder = colors["tooltipBorder"]
segmentBorder = colors["segmentBorder"]
containerBackground = colors["containerBackground"]
containerBorder = colors["containerBorder"]

# JS theme detector – reactive without refresh, no polling
components.html("""
<script>
(function() {
  function getIsDark() {
    try {
      const mql = window.matchMedia('(prefers-color-scheme: dark)');
      const htmlTheme = window.parent.document.documentElement.getAttribute('data-theme');
      const bodyTheme = window.parent.document.body.getAttribute('data-theme');
      const hasDarkClass = window.parent.document.documentElement.classList.contains('dark') || window.parent.document.body.classList.contains('dark');
      const streamlitDark = htmlTheme === 'dark' || bodyTheme === 'dark' || hasDarkClass;
      const appBg = getComputedStyle(window.parent.document.documentElement).getPropertyValue('--app-bg').trim();
      const isDarkBg = appBg === '#09090B' || appBg === '#0B0F14' || appBg === '#18181B';
      return streamlitDark || isDarkBg || mql.matches;
    } catch(e) { return str(isDark.lower()); }
  }
  function applyTheme(isDark) {
    const bg = isDark ? '#0B0F14' : '#FFFFFF';
    const text = isDark ? '#F8FAFC' : '#0F172A';
    const legend = isDark ? '#E2E8F0' : '#334155';
    const segBorder = isDark ? '#0B0F14' : '#FFFFFF';
    const tooltipBg = isDark ? '#111827' : '#FFFFFF';
    const tooltipText = isDark ? '#F8FAFC' : '#0F172A';
    const tooltipBorder = isDark ? '#334155' : '#CBD5E1';
    try {
      const plots = window.parent.document.querySelectorAll('.js-plotly-plot');
      plots.forEach(div => {
        // Find Plotly instance - try both window and window.parent
        const PlotlyObj = window.parent.Plotly || window.Plotly;
        if (PlotlyObj && div.data) {
          PlotlyObj.relayout(div, {
            'paper_bgcolor': 'rgba(0,0,0,0)',
            'plot_bgcolor': 'rgba(0,0,0,0)',
            'font.color': text,
            'title.font.color': text,
            'legend.font.color': legend
          });
          PlotlyObj.restyle(div, {'marker.line.color': segBorder}, [0]);
          // Update hoverlabel
          PlotlyObj.relayout(div, {'hoverlabel.bgcolor': tooltipBg, 'hoverlabel.font.color': tooltipText, 'hoverlabel.bordercolor': tooltipBorder});
        }
        // Update outsidetextfont via relayout not needed - CSS will handle, but try
        const texts = div.querySelectorAll('text');
        texts.forEach(t => {
          // Let CSS var handle, but force if needed
          // t.style.fill = text;
        });
        const container = div.closest('[data-testid="stPlotlyChart"]');
        if (container) {
          container.style.backgroundColor = bg;
          container.style.borderColor = isDark ? '#334155' : '#CBD5E1';
        }
        // Also update our custom container
        const custom = window.parent.document.querySelector('[data-testid="sector-donut-container"]');
        if (custom) {
          custom.style.backgroundColor = bg;
          custom.style.borderColor = isDark ? '#334155' : '#CBD5E1';
        }
      });
    } catch(e) {}
    try {
      const url = new URL(window.parent.location.href);
      const desired = isDark ? 'dark' : 'light';
      if (url.searchParams.get('theme') !== desired) {
        url.searchParams.set('theme', desired);
        window.parent.history.replaceState({}, '', url);
      }
    } catch(e) {}
  }
  let currentDark = getIsDark();
  // Apply immediately and after short delay to ensure Plotly loaded
  applyTheme(currentDark);
  setTimeout(() => applyTheme(getIsDark()), 500);
  setTimeout(() => applyTheme(getIsDark()), 1500);
  try {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => { currentDark = e.matches; applyTheme(e.matches); });
  } catch(e) {
    try { window.matchMedia('(prefers-color-scheme: dark)').addListener(e => { currentDark = e.matches; applyTheme(e.matches); }); } catch(e2) {}
  }
  const obs = new MutationObserver(() => {
    const nd = getIsDark();
    if (nd !== currentDark) { currentDark = nd; applyTheme(nd); }
  });
  try {
    obs.observe(window.parent.document.documentElement, {attributes:true, attributeFilter:['data-theme','class','style']});
    obs.observe(window.parent.document.body, {attributes:true, attributeFilter:['data-theme','class','style']});
    // Also observe app container for theme changes
    const appView = window.parent.document.querySelector('[data-testid="stAppViewContainer"]');
    if (appView) obs.observe(appView, {attributes:true, childList:true, subtree:true});
  } catch(e) {}
})();
</script>
""", height=0)

st.title("🏠 Home — Market Overview")
try:
    kinetic_marquee(["100 COMPANIES — 10 SECTORS — COMPOSITE SCORE TOP-5", "FINANCIAL INTELLIGENCE PLATFORM — HOME"], variant="muted", speed="normal")
except Exception:
    pass

# --- Year selector in sidebar (2019-2024) ---
year = st.sidebar.selectbox("Select Year", [2019, 2020, 2021, 2022, 2023, 2024], index=5)
st.sidebar.caption("Home metrics update for selected year where applicable.")

comps = get_companies()
ratios = get_ratios()
# Filter ratios for selected year for KPI computation
ratios_year = ratios[ratios["year"].astype(str) == str(year)].copy() if not ratios.empty else pd.DataFrame()

# Also need D/E and P/E: D/E from financial_ratios, P/E from stock_prices (market_cap)
import pathlib, sqlite3
DB_PATH = pathlib.Path("data/nifty100.db")
if not DB_PATH.exists():
    DB_PATH = pathlib.Path(__file__).resolve().parents[1] / "data" / "nifty100.db"
try:
    con = sqlite3.connect(str(DB_PATH))
    sp_year = pd.read_sql("SELECT company_id, pe_ratio FROM stock_prices WHERE date LIKE ?", con, params=(f"{year}%",))
    if sp_year.empty:
        sp_all = pd.read_sql("SELECT company_id, date, pe_ratio FROM stock_prices", con)
        sp_all["yr"] = pd.to_datetime(sp_all["date"], errors="coerce").dt.year.astype(str)
        sp_year = sp_all[sp_all["yr"] == str(year)][["company_id", "pe_ratio"]]
    con.close()
except Exception:
    sp_year = pd.DataFrame(columns=["company_id","pe_ratio"])

# --- 6 KPI tiles ---
def safe_mean(s):
    return s.dropna().mean() if not s.empty else np.nan
def safe_median(s):
    return s.dropna().median() if not s.empty else np.nan

avg_roe = safe_mean(ratios_year["return_on_equity_pct"]) if not ratios_year.empty else np.nan
median_pe = safe_median(sp_year["pe_ratio"]) if not sp_year.empty else np.nan
median_de = safe_median(ratios_year["debt_to_equity"]) if not ratios_year.empty else np.nan
total_companies = len(comps)
median_rev_cagr = safe_median(ratios_year["revenue_cagr_5yr"]) if not ratios_year.empty and "revenue_cagr_5yr" in ratios_year.columns else np.nan
if not ratios_year.empty:
    debt_free_count = len(ratios_year[(ratios_year["debt_to_equity"] == 0) | (ratios_year["icr_label"] == "Debt Free")])
else:
    debt_free_count = 0

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    st.metric("Average ROE", f"{avg_roe:.1f}%" if pd.notna(avg_roe) else "N/A", help=f"Average ROE % across companies in {year}")
with c2:
    st.metric("Median P/E", f"{median_pe:.1f}" if pd.notna(median_pe) else "N/A", help=f"Median P/E in {year} (stock_prices)")
with c3:
    st.metric("Median D/E", f"{median_de:.2f}" if pd.notna(median_de) else "N/A", help=f"Median Debt/Equity in {year}")
with c4:
    st.metric("Total Companies", str(total_companies))
with c5:
    st.metric("Median Rev CAGR 5Y", f"{median_rev_cagr:.1f}%" if pd.notna(median_rev_cagr) else "N/A")
with c6:
    st.metric("Debt-Free Companies", str(debt_free_count), help="D/E == 0 or ICR label Debt Free")

st.markdown("---")

# --- Sector breakdown donut chart — YEAR-AWARE + THEME-AWARE ---
st.subheader("Sector Breakdown")
# Year-aware: use selected_year from sidebar (do NOT use static sectors.company_count)
try:
    sector_data = get_sector_breakdown_by_year(year)
    if sector_data is None or sector_data.empty:
        st.warning(f"No sector data available for {year}")
        sector_counts = pd.DataFrame(columns=["sector", "count"])
    else:
        # get_sector_breakdown_by_year returns sector, company_count
        sector_counts = sector_data.rename(columns={"sector": "sector", "company_count": "count"})
        # Ensure sorted DESC for consistent donut
        sector_counts = sector_counts.sort_values("count", ascending=False)
except Exception as e:
    st.warning(f"Could not load sector breakdown for {year}: {e}")
    sector_counts = pd.DataFrame(columns=["sector", "count"])

# Handle empty after query
if sector_counts.empty:
    st.info(f"No sector data available for {year}")
    st.stop()
# Spec palette – saturated, works on both #0B0F14 and #FFFFFF
HIGH_CONTRAST_PALETTE = [
    "#14B8A6",
    "#3B82F6",
    "#F59E0B",
    "#EF4444",
    "#8B5CF6",
    "#F97316",
    "#10B981",
    "#EC4899",
    "#7C3AED",
    "#06B6D4",
    "#D946EF",
]

fig_donut = px.pie(
    sector_counts,
    names="sector",
    values="count",
    hole=0.55,
    title="Companies by 10 Sectors",
    color_discrete_sequence=HIGH_CONTRAST_PALETTE,
)
# Theme-aware traces – never hard-code one text color
fig_donut.update_traces(
    textposition="outside",
    textinfo="percent+label",
    texttemplate="<b>%{percent:.0%}</b> %{label}",
    hovertemplate="<b>%{label}</b><br>%{value} companies (%{percent})<extra></extra>",
    marker=dict(line=dict(color=segmentBorder, width=3)),
    outsidetextfont=dict(color=chartTextColor, size=11, family="Inter, sans-serif"),
    insidetextfont=dict(color=chartTextColor, size=12, family="Inter, sans-serif"),
    textfont=dict(color=chartTextColor, family="Inter, sans-serif"),
    pull=[0.025 if v <= sector_counts["count"].quantile(0.35) else 0 for v in sector_counts["count"]],
    hoverlabel=dict(bgcolor=tooltipBackground, font=dict(color=tooltipText, family="Inter, sans-serif", size=12), bordercolor=tooltipBorder),
)

fig_donut.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=chartTextColor, family="Inter, sans-serif", size=12),
    title=dict(
        text="Companies by 10 Sectors",
        font=dict(color=chartTextColor, family="Space Grotesk, Inter, sans-serif", size=16),
        x=0.5, xanchor="center",
    ),
    margin=dict(t=60, b=80, l=30, r=30),
    height=500,
    showlegend=True,
    legend=dict(
        orientation="h",
        y=-0.18,
        x=0.5,
        xanchor="center",
        yanchor="top",
        font=dict(color=legendColor, size=10, family="Inter, sans-serif"),
        bgcolor="rgba(0,0,0,0)",
        bordercolor=containerBorder,
        borderwidth=0,
        itemsizing="constant",
    ),
    uniformtext_minsize=10,
    uniformtext_mode="hide",
    hoverlabel=dict(bgcolor=tooltipBackground, font=dict(color=tooltipText, size=12, family="Inter, sans-serif"), bordercolor=tooltipBorder),
)

# Apply theme helper then re-apply theme-aware colors (helper sets transparent)
fig_donut = apply_plotly_theme(fig_donut)
# Re-apply theme-aware colors after helper - keep transparent bg, theme text
fig_donut.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=chartTextColor, family="Inter, sans-serif"),
    title_font_color=chartTextColor,
    legend_font_color=legendColor,
)
# Update traces again after helper
fig_donut.update_traces(
    marker=dict(line=dict(color=segmentBorder, width=3)),
    outsidetextfont=dict(color=chartTextColor, size=11, family="Inter, sans-serif"),
    insidetextfont=dict(color=chartTextColor, size=12, family="Inter, sans-serif"),
    hoverlabel=dict(bgcolor=tooltipBackground, font=dict(color=tooltipText), bordercolor=tooltipBorder),
)

# Wrap chart in theme-aware container - uses CSS variables for instant reactivity
st.markdown(f"""
<div style="background:{containerBackground}; border:2px solid {containerBorder}; padding:16px; border-radius:0px;" data-testid="sector-donut-container">
""", unsafe_allow_html=True)
st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False})
st.markdown("</div>", unsafe_allow_html=True)

# Inject CSS for Plotly text to follow theme via CSS variables - reactive without Python rerun
st.markdown(f"""
<style>
/* Use CSS variables so theme switch is instant via CSS, Python hex is fallback for first paint */
.js-plotly-plot .plotly text, .js-plotly-plot .gtitle {{
    fill: var(--app-text, {chartTextColor}) !important;
    color: var(--app-text, {chartTextColor}) !important;
    transition: fill 0.2s ease, color 0.2s ease;
}}
.js-plotly-plot .legend text {{
    fill: var(--app-text-secondary, {legendColor}) !important;
    color: var(--app-text-secondary, {legendColor}) !important;
}}
/* Sector donut hover tooltip only. The generic `.js-plotly-plot .plotly text` rule
   above also lands on Plotly's hover-label text (it lives inside .plotly) and forces
   `fill` with !important, so the label takes the page text colour regardless of
   hoverlabel.font.color. Scope a higher-specificity exception to the hover layer so
   only the tooltip is affected, and drive its colours from the theme CSS variables
   (always in sync with the browser, unlike the Python-side first-render guess) so the
   tooltip is correct on the very first paint, in both Dark and Light. Normal chart
   labels, legend and title are untouched. */
[data-testid="stPlotlyChart"] .js-plotly-plot g.hoverlayer g.hovertext text {{
    fill: var(--app-text, {chartTextColor}) !important;
    color: var(--app-text, {chartTextColor}) !important;
}}
[data-testid="stPlotlyChart"] .js-plotly-plot g.hoverlayer g.hovertext > path,
[data-testid="stPlotlyChart"] .js-plotly-plot g.hoverlayer g.hovertext > rect.bg {{
    fill: var(--app-surface, {tooltipBackground}) !important;
    stroke: var(--app-border, {tooltipBorder}) !important;
}}
[data-testid="stPlotlyChart"], [data-testid="sector-donut-container"] {{
    background: var(--app-bg, {containerBackground}) !important;
    border: 2px solid var(--app-border, {containerBorder}) !important;
    transition: background-color 0.2s ease, border-color 0.2s ease;
}}
.js-plotly-plot {{
    background: transparent !important;
}}
</style>
""", unsafe_allow_html=True)

st.caption(f"Sectors: {', '.join(sorted(comps['broad_sector'].dropna().unique()))} — total {sector_counts['sector'].nunique()} shown.")

# --- Top-5 by composite quality score ---
st.subheader("Top 5 — Composite Quality Score")
try:
    if not ratios_year.empty and "composite_quality_score" in ratios_year.columns:
        top = ratios_year.dropna(subset=["composite_quality_score"]).sort_values("composite_quality_score", ascending=False).head(5)
        top = top.merge(comps[["company_id", "company_name", "broad_sector"]], on="company_id", how="left")
        display_cols = ["company_id", "company_name", "broad_sector", "composite_quality_score", "return_on_equity_pct", "return_on_capital_employed_pct", "debt_to_equity"]
        display_cols = [c for c in display_cols if c in top.columns]
        st.dataframe(
            top[display_cols].style.format({"composite_quality_score": "{:.1f}", "return_on_equity_pct": "{:.1f}", "return_on_capital_employed_pct": "{:.1f}", "debt_to_equity": "{:.2f}"}, na_rep="N/A"),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Composite quality score not available for selected year.")
except Exception as e:
    st.warning(f"Could not compute top-5: {e}")

st.markdown("---")
st.markdown(f"**Year selected:** {year} — switch year in sidebar to update Average ROE, Median P/E, Median D/E, Median Revenue CAGR and Debt-Free count.")
