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

from src.dashboard.utils.db import get_cf, get_companies

st.set_page_config(page_title="Capital Allocation — Financial Intelligence Platform", layout="wide")
try:
    from src.dashboard.utils.theme import inject_kinetic_theme, kinetic_marquee, apply_plotly_theme
    inject_kinetic_theme()
except Exception:
    pass
st.title("🗺️ Capital Allocation Map")
try:
    kinetic_marquee(["CAPITAL ALLOCATION — 8 PATTERNS — TREEMAP", "CFO × CFI × CFF"], variant="muted", speed="normal")
except Exception:
    pass

cf = get_cf()
comps = get_companies()

cf["year_int"] = pd.to_numeric(cf["year"], errors="coerce")
latest = cf.sort_values("year_int").groupby("company_id").tail(1).copy()
latest = latest.merge(comps[["company_id","company_name","broad_sector"]], on="company_id", how="left")

# Classify 8 capital allocation patterns based on sign of CFO, CFI, CFF (spec Day 11/32)
# (+,-,-) Reinvestor | (+,+,-) Liquidating Assets | (-,+,+) Distress Signal
# (-,-,+) Growth Funded by Debt | (+,+,+) Cash Accumulator | (-,-,-) Pre-Revenue
# (+,-,+) Mixed | (-,+,-) Mixed (non-canonical corner)
PATTERN_MAP = {
    ("pos", "neg", "neg"): "Reinvestor",
    ("pos", "pos", "neg"): "Liquidating Assets",
    ("neg", "pos", "pos"): "Distress Signal",
    ("neg", "neg", "pos"): "Growth Funded by Debt",
    ("pos", "pos", "pos"): "Cash Accumulator",
    ("neg", "neg", "neg"): "Pre-Revenue",
    ("pos", "neg", "pos"): "Mixed",
    ("neg", "pos", "neg"): "Mixed",
}

def classify(r):
    cfo = r.get("operating_activity")
    cfi = r.get("investing_activity")
    cff = r.get("financing_activity")
    # Treat NaN/None as 0 for sign
    cfo = 0 if pd.isna(cfo) else cfo
    cfi = 0 if pd.isna(cfi) else cfi
    cff = 0 if pd.isna(cff) else cff
    key = ("pos" if cfo > 0 else "neg", "pos" if cfi > 0 else "neg", "pos" if cff > 0 else "neg")
    return PATTERN_MAP.get(key, f"CFO:{key[0]} CFI:{key[1]} CFF:{key[2]}")

latest["pattern"] = latest.apply(classify, axis=1)
latest["abs_cfo"] = latest["operating_activity"].abs().fillna(500)
latest["abs_cfo"] = latest["abs_cfo"].clip(lower=100)

# Ensure all 8 patterns represented in order for stable treemap
all_patterns = list(PATTERN_MAP.values())

fig = px.treemap(
    latest,
    path=["pattern", "company_id"],
    values="abs_cfo",
    color="broad_sector",
    hover_data={"company_name": True, "operating_activity": ":.0f", "investing_activity": ":.0f", "financing_activity": ":.0f", "abs_cfo": False},
    title="Treemap — 92 Companies grouped by 8 Capital Allocation Patterns (sized by |CFO|, coloured by sector)",
    color_discrete_sequence=px.colors.qualitative.Pastel,
)
fig.update_layout(height=600, margin=dict(l=10, r=10, t=50, b=10))
fig.update_traces(textinfo="label+value", hovertemplate="<b>%{label}</b><br>CFO: %{customdata[1]:,.0f}<extra></extra>")
st.plotly_chart(fig, use_container_width=True)
st.caption("Treemap sized by |CFO| — clicking a pattern zooms into its companies (Plotly treemap drill-down). Patterns derived from CFO/CFI/CFF signs.")

# Pattern selector — clicking a pattern shows list of companies in that pattern
st.markdown("### Explore by Pattern")
patterns_available = sorted(latest["pattern"].unique().tolist())
selected_pattern = st.selectbox("Select a capital allocation pattern", patterns_available, index=0)
subset = latest[latest["pattern"] == selected_pattern].copy()
st.markdown(f"**{selected_pattern}** — {len(subset)} companies")
# Show table sorted by CFO
subset = subset.sort_values("operating_activity", ascending=False)
display_cols = ["company_id","company_name","broad_sector","operating_activity","investing_activity","financing_activity","pattern"]
display_cols = [c for c in display_cols if c in subset.columns]
st.dataframe(subset[display_cols].style.format(na_rep="N/A", precision=0), use_container_width=True, hide_index=True, height=400)

# Summary counts per pattern
st.markdown("**Count per Pattern**")
counts = latest["pattern"].value_counts().reset_index()
counts.columns = ["pattern","count"]
st.dataframe(counts, use_container_width=True, hide_index=True)