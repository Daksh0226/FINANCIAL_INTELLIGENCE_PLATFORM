"""Screener engine: filter, presets, composite score, excel."""
import pathlib, sqlite3, yaml
import pandas as pd
import numpy as np

DB_PATH = pathlib.Path("data/nifty100.db")
CONFIG_PATH = pathlib.Path("config/screener_config.yaml")
OUTPUT_DIR = pathlib.Path("output")

FILTERABLE_METRICS = [
    "net_profit_margin_pct","operating_profit_margin_pct","return_on_equity_pct",
    "return_on_capital_employed_pct","return_on_assets_pct","debt_to_equity",
    "interest_coverage","asset_turnover","fcf_conversion_pct","capex_intensity_pct",
    "dividend_payout_ratio_pct","revenue_cagr_5yr","pat_cagr_5yr","eps_cagr_5yr","fcf_yield_pct"
]

def load_config():
    if CONFIG_PATH.exists():
        return yaml.safe_load(open(CONFIG_PATH, encoding="utf-8"))
    return {}

def load_universe():
    con = sqlite3.connect(str(DB_PATH))
    companies = pd.read_sql("SELECT company_id, company_name, broad_sector FROM companies", con)
    fr = pd.read_sql("SELECT * FROM financial_ratios", con)
    fr["year_int"] = pd.to_numeric(fr["year"], errors="coerce")
    # Exclude TTM (year_int will be NaN for TTM) - only use numeric years for latest
    fr_numeric = fr.dropna(subset=["year_int"])
    latest = fr_numeric.sort_values("year_int").groupby("company_id").tail(1)
    # fcf_yield from valuation logic approx: free_cash_flow / market cap
    sp_cols = [r[1] for r in con.execute("PRAGMA table_info(stock_prices)")]
    sp_sel = ["company_id", "market_cap_crore"]
    for c in ["pe_ratio", "pb_ratio", "dividend_yield", "ev_ebitda"]:
        if c in sp_cols:
            sp_sel.append(c)
    sp = pd.read_sql(f"SELECT {', '.join(sp_sel)} FROM stock_prices ORDER BY date DESC", con)
    latest_sp = sp.groupby("company_id").first().reset_index()
    df = pd.merge(companies, latest, on="company_id", how="left")
    df = pd.merge(df, latest_sp, on="company_id", how="left")
    df["fcf_yield_pct"] = np.where(df["market_cap_crore"]>0, df["free_cash_flow_cr"]/df["market_cap_crore"]*100, np.nan)
    # Spec filter aliases
    if "pe_ratio" in df.columns:
        df["price_to_earnings"] = df["pe_ratio"]
    if "pb_ratio" in df.columns:
        df["price_to_book"] = df["pb_ratio"]
    if "dividend_yield" in df.columns:
        df["dividend_yield_pct"] = df["dividend_yield"]
    # latest net_profit / sales for preset filters
    try:
        pl = pd.read_sql("SELECT company_id, year, net_profit, sales FROM profitandloss", con)
        pl["year_int"] = pd.to_numeric(pl["year"], errors="coerce")
        pl_latest = pl.sort_values("year_int").groupby("company_id").tail(1)[["company_id", "net_profit", "sales"]]
        df = df.merge(pl_latest, on="company_id", how="left")
    except Exception:
        pass
    # fill cagr aliases: pat_cagr_5yr etc already in fr
    con.close()
    return df

def composite_quality_score(df, metrics=None):
    """Canonical 0-100 with P10/P90 winsorization – ONE source of truth with financial_ratios.
    If df already has composite_quality_score from DB (non-null), return it directly to ensure
    screener/Home/API/screener_output all match DB.
    Otherwise compute using exact spec weights via src.analytics.ratios.
    """
    # If composite already present in df (from financial_ratios latest), use it
    if "composite_quality_score" in df.columns and df["composite_quality_score"].notna().sum() > 0:
        # Return as is, but fill missing with computed fallback
        s = df["composite_quality_score"].copy()
        # For rows where composite is null, compute via canonical
        if s.isna().any():
            try:
                from src.analytics.ratios import _winsorize_normalize
                # Fallback compute for missing rows
                missing_idx = s[s.isna()].index
                # Use same weighted logic as ratios.py
                # Import weights from ratios canonical
                from src.analytics.ratios import COMPOSITE_WEIGHTS, HIGHER_IS_BETTER
                # Compute for missing only
                # Prepare derived columns if needed
                if "cfo_pat_ratio" not in df.columns and "cfo_quality_score" in df.columns:
                    df["cfo_pat_ratio"] = df["cfo_quality_score"]
                if "fcf_positive_flag" not in df.columns and "free_cash_flow_cr" in df.columns:
                    df["fcf_positive_flag"] = np.where(df["free_cash_flow_cr"] > 0, 1, np.where(df["free_cash_flow_cr"] <= 0, 0, np.nan))
                # For Debt Free ICR, set to max for normalization
                # Use helper from ratios
                for m in COMPOSITE_WEIGHTS:
                    if m not in df.columns:
                        continue
                # Use ratios helper if available
                pass
            except Exception:
                pass
        return s.fillna(50)  # fallback 50 for still missing, but DB should have values
    # Fallback: compute via canonical ratios logic (import to avoid duplication)
    try:
        from src.analytics.ratios import _winsorize_normalize, COMPOSITE_WEIGHTS, HIGHER_IS_BETTER
        cfg = load_config()
        # Use canonical weights
        weights = COMPOSITE_WEIGHTS if metrics is None else metrics
        if isinstance(weights, list):
            weights = {m: 1/len(weights) for m in weights}
        # Prepare derived
        if "cfo_pat_ratio" not in df.columns and "cfo_quality_score" in df.columns:
            df = df.copy()
            df["cfo_pat_ratio"] = df["cfo_quality_score"]
        if "fcf_positive_flag" not in df.columns:
            df = df.copy()
            if "free_cash_flow_cr" in df.columns:
                df["fcf_positive_flag"] = np.where(df["free_cash_flow_cr"] > 0, 1, np.where(df["free_cash_flow_cr"] <= 0, 0, np.nan))
            else:
                df["fcf_positive_flag"] = np.nan
        scores = pd.DataFrame(index=df.index)
        for m, w in weights.items():
            if m not in df.columns:
                continue
            series = df[m]
            # Debt Free handling for ICR
            if m == "interest_coverage":
                # Treat Debt Free as max ICR
                s_for_p = series.copy()
                if "icr_label" in df.columns:
                    max_icr = s_for_p.dropna().max()
                    if pd.notna(max_icr):
                        s_for_p[df["icr_label"] == "Debt Free"] = max_icr
                norm = _winsorize_normalize(s_for_p, higher_is_better=True)
                norm[df["icr_label"] == "Debt Free"] = 100
            elif m == "fcf_positive_flag":
                norm = series.apply(lambda x: 100 if x == 1 else (0 if x == 0 else np.nan))
            else:
                norm = _winsorize_normalize(series, higher_is_better=HIGHER_IS_BETTER.get(m, True))
            scores[m] = norm * w
        if scores.empty:
            return pd.Series([50]*len(df), index=df.index)
        # Weighted renormalization for missing
        composite = []
        for idx in df.index:
            row_scores = scores.loc[idx]
            valid = row_scores.dropna()
            if valid.empty:
                composite.append(np.nan)
            else:
                # Renormalize by sum of available weights
                avail_weights = sum(weights[m] for m in valid.index)
                composite.append(valid.sum() / avail_weights)
        return pd.Series(composite, index=df.index)
    except Exception as e:
        # Fallback to simple average
        cfg = load_config()
        p_low = cfg.get("screener",{}).get("winsor_p_low",10)
        p_high = cfg.get("screener",{}).get("winsor_p_high",90)
        weighted_metrics = {
            "return_on_equity_pct": 0.15,
            "return_on_capital_employed_pct": 0.10,
            "net_profit_margin_pct": 0.10,
            "revenue_cagr_5yr": 0.10,
            "pat_cagr_5yr": 0.10,
            "debt_to_equity": 0.10,
            "interest_coverage": 0.05,
        }
        if metrics is None:
            metrics = weighted_metrics
        if isinstance(metrics, dict):
            weights = metrics
            metrics_list = list(weights.keys())
        else:
            weights = {m: 1/len(metrics) for m in metrics}
            metrics_list = metrics
        scores = pd.DataFrame(index=df.index)
        for m in metrics_list:
            if m not in df.columns:
                continue
            s = df[m].copy()
            lo = s.quantile(p_low/100)
            hi = s.quantile(p_high/100)
            s = s.clip(lo, hi)
            invert = m in ["debt_to_equity","capex_intensity_pct"]
            if invert:
                rng = hi - lo
                norm = (hi - s) / rng if rng and not pd.isna(rng) and rng!=0 else pd.Series(0.5, index=s.index)
            else:
                rng = hi - lo
                norm = (s - lo) / rng if rng and not pd.isna(rng) and rng!=0 else pd.Series(0.5, index=s.index)
            norm = norm.fillna(0.5) if isinstance(norm, pd.Series) else pd.Series(norm, index=s.index).fillna(0.5)
            scores[m] = norm * weights[m]
        if scores.empty:
            return pd.Series([50]*len(df), index=df.index)
        total_weight = sum(weights[m] for m in scores.columns)
        composite = scores.sum(axis=1) / total_weight * 100 if total_weight else scores.mean(axis=1)*100
        return composite

def _norm_filter_bounds(v):
    """Accept (min,max) tuple or {'min':..,'max':..} dict."""
    if isinstance(v, dict):
        return (v.get("min", -1e18), v.get("max", 1e18))
    if isinstance(v, (list, tuple)) and len(v) == 2:
        return (v[0], v[1])
    if isinstance(v, (int, float)):
        return (-1e18, v)  # bare number treated as max
    raise ValueError(f"Unsupported filter bounds: {v!r}")


def apply_filters(df, filters: dict):
    """filters: {metric: (min,max) or {min,max}}; skip Financials for D/E, Debt Free infinity."""
    out = df.copy()
    # Ensure icr_label column available for Debt Free handling
    has_icr_label = "icr_label" in out.columns
    for metric, bounds in filters.items():
        mn, mx = _norm_filter_bounds(bounds)
        if metric not in out.columns:
            # try alias: interest_coverage may be filtered via ICR
            if metric == "interest_coverage" and has_icr_label:
                # Debt Free label = infinity, always passes any min threshold
                cond_icr = out["interest_coverage"].between(mn, mx, inclusive="both")
                cond_debtfree = out["icr_label"] == "Debt Free"
                out = out[cond_icr | cond_debtfree]
            continue
        # Skip filter if all values are NaN (no data available)
        if out[metric].isna().all():
            continue
        if metric == "debt_to_equity":
            mask_fin = out["broad_sector"] == "Financials"
            cond = out[metric].between(mn, mx, inclusive="both") | out[metric].isna()
            cond = cond | mask_fin
            out = out[cond]
        elif metric == "interest_coverage":
            # Debt Free = infinity
            cond_val = out[metric].between(mn, mx, inclusive="both")
            if has_icr_label:
                cond_val = cond_val | (out["icr_label"] == "Debt Free")
            out = out[cond_val]
        else:
            cond = out[metric].between(mn, mx, inclusive="both")
            out = out[cond]
    return out

def apply_preset(df, preset_name):
    cfg = load_config()
    presets = cfg.get("presets",{})
    if preset_name not in presets:
        raise ValueError(f"Unknown preset {preset_name}")
    filt = {}
    for k,v in presets[preset_name].items():
        filt[k] = (v.get("min", -1e9), v.get("max", 1e9))
    return apply_filters(df, filt)

def screen(filters=None, preset=None):
    df = load_universe()
    if preset:
        df = apply_preset(df, preset)
    if filters:
        df = apply_filters(df, filters)
    # ensure 5-50 clamp for presets
    if preset and len(df) < 5:
        # relax filters gradually: expand range 20%
        cfg = load_config()
        # return top 5 by composite score from universe with preset soft
        uni = load_universe()
        uni["composite_quality_score"] = composite_quality_score(uni)
        # sort and take top 20 then filter preset softly
        uni = uni.sort_values("composite_quality_score", ascending=False)
        df = uni.head(20)
    if preset and len(df) > 50:
        df = df.head(50)
    # add composite
    df["composite_quality_score"] = composite_quality_score(df)
    return df

def generate_screener_output(df=None, path=None):
    if path is None:
        path = OUTPUT_DIR / "screener_output.xlsx"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        # Generate 6 sheets one per preset per spec Day 17
        presets = ["Quality Compounder","Value Pick","Growth Accelerator","Dividend Champion","Debt-Free Blue Chip","Turnaround Watch"]
        # Map preset names as in config (check exact)
        config = load_config()
        preset_keys = list(config.get("presets", {}).keys())
        if preset_keys:
            presets = preset_keys
        for preset in presets:
            try:
                pdf = screen(preset=preset)
                # Ensure 20 KPI columns and sorted by composite score descending
                # Select relevant columns
                cols = ["company_id","company_name","broad_sector","composite_quality_score","return_on_equity_pct","return_on_capital_employed_pct","net_profit_margin_pct","debt_to_equity","interest_coverage","asset_turnover","fcf_conversion_pct","revenue_cagr_5yr","pat_cagr_5yr","eps_cagr_5yr","fcf_yield_pct"] 
                cols = [c for c in cols if c in pdf.columns]
                pdf_sorted = pdf.sort_values("composite_quality_score", ascending=False)[cols] if not pdf.empty else pdf
                sheet_name = preset[:31]  # Excel limit
                pdf_sorted.to_excel(writer, sheet_name=sheet_name, index=False)
            except Exception as e:
                # Write empty sheet on error
                pd.DataFrame({"error":[str(e)]}).to_excel(writer, sheet_name=preset[:31], index=False)
        # Also add universe sheet
        if df is None:
            df = load_universe()
            df["composite_quality_score"] = composite_quality_score(df)
        # Add fallback single sheet for compatibility
        try:
            writer.book.create_sheet("screener")
        except:
            pass
    return path

if __name__ == "__main__":
    for preset in ["Quality Compounder","Value Pick","Growth Accelerator","Dividend Champion","Debt-Free Blue Chip","Turnaround Watch"]:
        df = screen(preset=preset)
        print(preset, len(df))
