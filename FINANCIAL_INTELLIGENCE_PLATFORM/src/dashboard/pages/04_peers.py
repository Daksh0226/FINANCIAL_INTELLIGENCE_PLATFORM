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
import plotly.graph_objects as go

from src.dashboard.utils.db import get_companies, get_peers, get_ratios, get_peer_percentiles

st.set_page_config(page_title="Peer Comparison — Financial Intelligence Platform", layout="wide")
try:
    from src.dashboard.utils.theme import inject_kinetic_theme, kinetic_marquee, apply_plotly_theme
    inject_kinetic_theme()
except Exception:
    pass
st.title("🤝 Peer Comparison")
try:
    kinetic_marquee(["PEER RADAR — 8 METRICS — 11 GROUPS", "BENCHMARK COMPARISON"], variant="muted", speed="normal")
except Exception:
    pass

comps = get_companies()
ratios = get_ratios()

# Peer group dropdown with all groups (11 groups expected)
try:
    DB_PATH = pathlib.Path("data/nifty100.db")
    if not DB_PATH.exists():
        DB_PATH = pathlib.Path(__file__).resolve().parents[1] / "data" / "nifty100.db"
    con = sqlite3.connect(str(DB_PATH))
    groups_df = pd.read_sql("SELECT DISTINCT peer_group_name FROM peer_groups ORDER BY peer_group_name", con)
    con.close()
    groups = groups_df["peer_group_name"].dropna().tolist()
except Exception:
    groups = []

if not groups:
    # Fallback: derive from broad_sector
    groups = sorted(comps["broad_sector"].dropna().unique().tolist())
    st.caption("Peer groups derived from sectors (peer_groups table empty or not found).")

selected_group = st.selectbox("Select peer group", groups, index=0) if groups else None

if not selected_group:
    st.warning("No peer groups available.")
    st.stop()

# Fetch all companies in selected group
from src.dashboard.utils.db import get_peers as _get_peers
peers_in_group = _get_peers(group_name=selected_group) if selected_group else pd.DataFrame()

# If peer_groups table doesn't map well (e.g. IT Services has SUNPHARMA), also consider sector-based fallback
if peers_in_group.empty:
    # Treat group as sector name
    peers_in_group = comps[comps["broad_sector"] == selected_group].copy()
    peers_in_group["peer_group_name"] = selected_group
    peers_in_group["is_benchmark"] = 0
else:
    peers_in_group = peers_in_group.copy()

company_ids_in_group = peers_in_group["company_id"].tolist()
st.caption(f"Peer group **{selected_group}** — {len(company_ids_in_group)} companies")

# Company selector within group (benchmark highlighted)
# Determine benchmark
benchmark_id = None
if "is_benchmark" in peers_in_group.columns:
    bench_rows = peers_in_group[peers_in_group["is_benchmark"] == 1]
    if not bench_rows.empty:
        benchmark_id = bench_rows.iloc[0]["company_id"]

# Options for radar's selected company
selected_ticker = st.selectbox(
    "Select company to compare (highlighted in KPI table)",
    company_ids_in_group,
    index=company_ids_in_group.index(benchmark_id) if benchmark_id in company_ids_in_group else 0,
    format_func=lambda x: f"{'⭐ ' if x == benchmark_id else ''}{x} — {comps.loc[comps['company_id']==x, 'company_name'].values[0] if x in comps['company_id'].values else x}",
)

# Prepare metrics for radar: 8 metrics vs peer group average using Scatterpolar
# Use latest ratios for group members
ratios["year_int"] = pd.to_numeric(ratios["year"], errors="coerce")
latest_ratios = ratios.sort_values("year_int").groupby("company_id").tail(1)

METRICS_8 = [
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "debt_to_equity",
    "interest_coverage",
    "asset_turnover",
    "revenue_cagr_5yr",
]
# Only keep metrics that exist and have data
metrics_available = [m for m in METRICS_8 if m in latest_ratios.columns]

group_latest = latest_ratios[latest_ratios["company_id"].isin(company_ids_in_group)].copy()
if group_latest.empty:
    st.warning("No ratio data for this peer group.")
    st.stop()

# Compute peer averages (median for robustness, treat NaN/inf)
# For D/E lower is better — keep raw; radar will show lower is more central or outer? We keep as-is for interpretability
peer_avg = group_latest[metrics_available].median(numeric_only=True)

# Selected company's values
sel_row = group_latest[group_latest["company_id"] == selected_ticker]
if sel_row.empty:
    st.warning(f"No data for {selected_ticker} in latest year.")
    sel_vals = [np.nan]*len(metrics_available)
else:
    sel_vals = sel_row[metrics_available].iloc[0].tolist()

# Normalize for radar display: min-max 0-1 per metric for visual comparability; handle inf/NaN -> 0.5
def normalize_series(series, vals, avg_vals):
    # Winsorize per metric across group
    norm_sel = []
    norm_avg = []
    labels = []
    for i, m in enumerate(metrics_available):
        s = group_latest[m].dropna().replace([np.inf, -np.inf], np.nan).dropna()
        if s.empty or s.nunique() < 2:
            norm_sel.append(0.5)
            norm_avg.append(0.5)
            labels.append(m.replace("_pct","").replace("_"," ").title())
            continue
        lo, hi = s.quantile(0.05), s.quantile(0.95)
        if hi == lo:
            norm_sel.append(0.5)
            norm_avg.append(0.5)
        else:
            # invert D/E so lower is better (outer is better)
            v_sel = vals[i]
            v_avg = avg_vals[m] if m in avg_vals else np.nan
            if m == "debt_to_equity":
                v_sel_n = (hi - v_sel) / (hi - lo) if pd.notna(v_sel) else 0.5
                v_avg_n = (hi - v_avg) / (hi - lo) if pd.notna(v_avg) else 0.5
            else:
                v_sel_n = (v_sel - lo) / (hi - lo) if pd.notna(v_sel) else 0.5
                v_avg_n = (v_avg - lo) / (hi - lo) if pd.notna(v_avg) else 0.5
            norm_sel.append(float(np.clip(v_sel_n, 0, 1)))
            norm_avg.append(float(np.clip(v_avg_n, 0, 1)))
        labels.append(m.replace("_pct","").replace("_"," ").title()[:16])
    return labels, norm_sel, norm_avg

labels, norm_sel, norm_avg = normalize_series(group_latest, sel_vals, peer_avg)

fig = go.Figure()
fig.add_trace(go.Scatterpolar(
    r=norm_sel + [norm_sel[0]] if norm_sel else [],
    theta=labels + [labels[0]] if labels else [],
    fill="toself",
    name=f"{selected_ticker} (Selected)",
    line_color="#4C78A8",
    fillcolor="rgba(76,120,168,0.25)",
))
fig.add_trace(go.Scatterpolar(
    r=norm_avg + [norm_avg[0]] if norm_avg else [],
    theta=labels + [labels[0]] if labels else [],
    fill="toself",
    name="Peer Group Median",
    line_color="#F58518",
    fillcolor="rgba(245,133,24,0.18)",
))
fig.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0, 1], tickvals=[0, 0.5, 1], ticktext=["Low","Mid","High"])),
    showlegend=True,
    title=f"Radar: {selected_ticker} vs Peer Group Average ({selected_group}) — normalized 0-1 (D/E inverted)",
    height=520,
    margin=dict(l=40, r=40, t=60, b=40),
    legend=dict(orientation="h", y=-0.15),
)
fig = apply_plotly_theme(fig)
st.plotly_chart(fig, use_container_width=True)
st.caption("Radar uses 5th/95th percentile winsorization per metric; Debt/Equity inverted so outer = better (lower leverage).")

# --- Side-by-side KPI table for all companies in group — highlight benchmark row ---
st.markdown("### Peer Group KPI Table")
# Build table: join company names
table = group_latest.merge(comps[["company_id","company_name","broad_sector"]], on="company_id", how="left")
cols_to_show = ["company_id","company_name","broad_sector"] + metrics_available
cols_to_show = [c for c in cols_to_show if c in table.columns]
# Sort by ROE descending where available
if "return_on_equity_pct" in table.columns:
    table = table.sort_values("return_on_equity_pct", ascending=False)

# Style: highlight benchmark/selected row — dark-mode high-contrast (fixes pale-yellow/white unreadable bug)
def highlight_benchmark(row):
    if row["company_id"] == benchmark_id or row["company_id"] == selected_ticker:
        return ["background-color: #1E3A5F; color: #F8FAFC; font-weight: 600; border: 1px solid #2A5A8A"] * len(row)
    return [""] * len(row)

# Also highlight selected ticker with different shade if not benchmark
st.dataframe(
    table[cols_to_show].style.apply(highlight_benchmark, axis=1).format(na_rep="N/A", precision=2),
    use_container_width=True,
    hide_index=True,
    height=400,
)
if benchmark_id:
    st.caption(f"⭐ Benchmark company for **{selected_group}**: **{benchmark_id}** — highlighted in yellow. Selected company **{selected_ticker}** also highlighted.")
else:
    st.caption(f"Selected company **{selected_ticker}** highlighted — no benchmark flagged for this group.")

# --- Peer percentile ranks (long format canonical) ---
st.markdown("### Peer Percentile Ranks (canonical long format)")
try:
    pct_df = get_peer_percentiles(company_id=selected_ticker)
    if not pct_df.empty:
        # Use latest year for display
        pct_df["year_int"] = pd.to_numeric(pct_df["year"], errors="coerce")
        latest_year = pct_df["year_int"].max()
        pct_latest = pct_df[pct_df["year_int"] == latest_year]
        # Pivot to show metric vs percentile
        pivot = pct_latest.pivot_table(index="metric", values=["value","percentile_rank"], aggfunc="first")
        # Format percentile as percent and show N/A for missing
        pct_latest_sorted = pct_latest.sort_values("metric")
        st.dataframe(pct_latest_sorted[["metric","value","percentile_rank","year"]].style.format(na_rep="N/A", precision=3), use_container_width=True, hide_index=True)
        st.caption(f"Percentile ranks for {selected_ticker} in {selected_group} year {int(latest_year) if pd.notna(latest_year) else 'N/A'} - 0 = lowest, 1 = highest. D/E inverted (lower is better). N/A indicates source missing or insufficient peers.")
    else:
        st.info(f"No peer percentile data for {selected_ticker} - may be MAPPING_MISSING (company not in peer group). Showing N/A.")
except Exception as e:
    st.warning(f"Could not load percentile ranks: {e}")