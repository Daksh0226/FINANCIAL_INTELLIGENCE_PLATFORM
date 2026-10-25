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

st.set_page_config(page_title="Screener — Financial Intelligence Platform", layout="wide")
try:
    from src.dashboard.utils.theme import inject_kinetic_theme, kinetic_marquee
    inject_kinetic_theme()
except Exception:
    pass
st.title("🔍 Screener")
try:
    kinetic_marquee(["SCREENER — 10 SLIDERS — 6 PRESETS — LIVE FILTERING", "QUALITY × VALUE × GROWTH"], variant="muted", speed="normal")
except Exception:
    pass

# Use screener engine for all filtering and presets
from src.screener.engine import load_universe, screen, composite_quality_score, apply_filters, load_config

# Load universe with all data
df_base = load_universe()

# Ensure composite score is present
if "composite_quality_score" not in df_base.columns or df_base["composite_quality_score"].isna().all():
    df_base["composite_quality_score"] = composite_quality_score(df_base)

# Preset definitions from config (matching config/screener_config.yaml)
PRESETS = {
    "Quality Compounder":   {"roe_min": 15, "de_max": 1.0, "fcf_min": 0,   "rev_cagr_min": 10, "pat_cagr_min": 0,  "opm_min": 0,  "pe_max": 100, "pb_max": 20, "div_min": 0, "icr_min": 0},
    "Value Pick":          {"roe_min": 0,  "de_max": 2.0, "fcf_min": -5000,"rev_cagr_min": -20,"pat_cagr_min": -30,"opm_min": 0,  "pe_max": 30,  "pb_max": 4,  "div_min": 1, "icr_min": 0},
    "Growth Accelerator":  {"roe_min": 0,  "de_max": 2.0, "fcf_min": -5000,"rev_cagr_min": 8,  "pat_cagr_min": 12, "opm_min": 0,  "pe_max": 100, "pb_max": 20, "div_min": 0, "icr_min": 0},
    "Dividend Champion":   {"roe_min": 0,  "de_max": 5.0, "fcf_min": 0,   "rev_cagr_min": -20,"pat_cagr_min": -30,"opm_min": 0,  "pe_max": 100, "pb_max": 20, "div_min": 2, "icr_min": 0},
    "Debt-Free Blue Chip": {"roe_min": 12, "de_max": 0.05,"fcf_min": -5000,"rev_cagr_min": -20,"pat_cagr_min": -30,"opm_min": 0,  "pe_max": 100, "pb_max": 20, "div_min": 0, "icr_min": 0},
    "Turnaround Watch":    {"roe_min": 0,  "de_max": 2.0, "fcf_min": 0,   "rev_cagr_min": 10, "pat_cagr_min": -30,"opm_min": 0,  "pe_max": 100, "pb_max": 20, "div_min": 0, "icr_min": 0},
}

# Initialize session state for preset
for k in ["roe_min","de_max","fcf_min","rev_cagr_min","pat_cagr_min","opm_min","pe_max","pb_max","div_min","icr_min"]:
    if k not in st.session_state:
        defaults = {"roe_min": 0, "de_max": 5, "fcf_min": -5000, "rev_cagr_min": -20, "pat_cagr_min": -30, "opm_min": -50, "pe_max": 100, "pb_max": 20, "div_min": 0, "icr_min": 0}
        st.session_state[k] = defaults[k]

st.sidebar.markdown("### 🔧 Filters — 10 Metrics")
st.sidebar.caption("Adjust sliders; results update live.")

# Preset buttons — 3 per row
st.sidebar.markdown("**Presets** — click to auto-fill sliders")
prow1 = st.sidebar.columns(3)
prow2 = st.sidebar.columns(3)
preset_cols = prow1 + prow2
for i, name in enumerate(PRESETS.keys()):
    display_name = name.upper()
    with preset_cols[i]:
        if st.button(display_name, use_container_width=True, key=f"preset_{name}"):
            for kk, vv in PRESETS[name].items():
                st.session_state[kk] = vv
            st.rerun()

st.sidebar.markdown("---")

# 10 sliders in sidebar
roe_min = st.sidebar.slider("ROE min (%)", -20.0, 50.0, float(st.session_state["roe_min"]), 0.5)
de_max = st.sidebar.slider("D/E max", 0.0, 5.0, float(st.session_state["de_max"]), 0.05)
fcf_min = st.sidebar.slider("FCF min (₹ Cr)", -5000.0, 20000.0, float(st.session_state["fcf_min"]), 100.0)
rev_cagr_min = st.sidebar.slider("Revenue CAGR min (%)", -20.0, 50.0, float(st.session_state["rev_cagr_min"]), 0.5)
pat_cagr_min = st.sidebar.slider("PAT CAGR min (%)", -30.0, 80.0, float(st.session_state["pat_cagr_min"]), 0.5)
opm_min = st.sidebar.slider("OPM min (%)", -50.0, 80.0, float(st.session_state["opm_min"]), 0.5)
pe_max = st.sidebar.slider("P/E max", 0.0, 100.0, float(st.session_state["pe_max"]), 0.5)
pb_max = st.sidebar.slider("P/B max", 0.0, 20.0, float(st.session_state["pb_max"]), 0.1)
div_min = st.sidebar.slider("Dividend Yield min (%)", 0.0, 10.0, float(st.session_state["div_min"]), 0.1)
icr_min = st.sidebar.slider("ICR min", 0.0, 100.0, float(st.session_state["icr_min"]), 0.5)

# Save back to session for preset persistence
st.session_state.update({
    "roe_min": roe_min, "de_max": de_max, "fcf_min": fcf_min,
    "rev_cagr_min": rev_cagr_min, "pat_cagr_min": pat_cagr_min,
    "opm_min": opm_min, "pe_max": pe_max, "pb_max": pb_max,
    "div_min": div_min, "icr_min": icr_min
})

# Apply filters using the engine's logic
# Build filter dict matching engine's metric names
filters = {
    "return_on_equity_pct": (roe_min, 1e9),
    "debt_to_equity": (0, de_max),
    "free_cash_flow_cr": (fcf_min, 1e9),
    "revenue_cagr_5yr": (rev_cagr_min, 1e9),
    "pat_cagr_5yr": (pat_cagr_min, 1e9),
    "operating_profit_margin_pct": (opm_min, 1e9),
}

# Add valuation filters only if data is available
if "price_to_earnings" in df_base.columns and df_base["price_to_earnings"].notna().any():
    filters["price_to_earnings"] = (0, pe_max)
if "price_to_book" in df_base.columns and df_base["price_to_book"].notna().any():
    filters["price_to_book"] = (0, pb_max)
if "dividend_yield_pct" in df_base.columns and df_base["dividend_yield_pct"].notna().any():
    filters["dividend_yield_pct"] = (div_min, 1e9)

filters["interest_coverage"] = (icr_min, 1e9)

# Apply filters
filtered = apply_filters(df_base, filters)

# Display result count
st.markdown(f"**{len(filtered)} companies match your filters**  out of {len(df_base)} total")
if filtered.empty:
    st.info("No companies match — relax sliders or try a different preset. Extreme slider values will not crash; they simply yield 0 results.")
else:
    # Sort by composite score
    filtered = filtered.sort_values("composite_quality_score", ascending=False)
    
    # Columns to show per spec
    show_cols = [
        "company_id", "company_name", "broad_sector", "composite_quality_score",
        "return_on_equity_pct", "debt_to_equity", "free_cash_flow_cr",
        "revenue_cagr_5yr", "pat_cagr_5yr", "operating_profit_margin_pct",
        "price_to_earnings", "price_to_book", "dividend_yield_pct", "interest_coverage"
    ]
    show_cols = [c for c in show_cols if c in filtered.columns]
    
    # Friendly headers
    rename = {
        "company_id": "company_id", "company_name": "name", "broad_sector": "sector",
        "composite_quality_score": "composite score", "return_on_equity_pct": "ROE %",
        "debt_to_equity": "D/E", "free_cash_flow_cr": "FCF (Cr)",
        "revenue_cagr_5yr": "Rev CAGR 5Y", "pat_cagr_5yr": "PAT CAGR 5Y",
        "operating_profit_margin_pct": "OPM %", "price_to_earnings": "P/E",
        "price_to_book": "P/B", "dividend_yield_pct": "Div Yield %", "interest_coverage": "ICR"
    }
    disp = filtered[show_cols].rename(columns=rename)
    
    # Display with styling
    st.dataframe(
        disp.style.format(na_rep="N/A", precision=2),
        use_container_width=True,
        hide_index=True,
        height=500,
    )

    # CSV download
    csv_bytes = filtered[show_cols].rename(columns=rename).to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download CSV",
        data=csv_bytes,
        file_name="screener_results.csv",
        mime="text/csv",
        help="Well-formed CSV with all visible columns",
        use_container_width=False,
    )
    st.caption("CSV export includes all visible columns with correct headers; missing values are empty (N/A in table).")

    # Show preset results summary
    with st.expander("📊 Preset Results Summary", expanded=False):
        for preset_name in PRESETS.keys():
            try:
                preset_df = screen(preset=preset_name)
                st.markdown(f"**{preset_name}**: {len(preset_df)} companies")
            except Exception as e:
                st.markdown(f"**{preset_name}**: Error - {e}")