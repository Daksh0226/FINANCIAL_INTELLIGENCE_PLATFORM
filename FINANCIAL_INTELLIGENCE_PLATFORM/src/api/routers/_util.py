"""Shared JSON-safe DataFrame serialization for API routers."""
import numpy as np
import pandas as pd


def records(df: pd.DataFrame | None):
    """Convert a DataFrame to JSON-safe records (NaN/NaT/inf -> None)."""
    if df is None or df.empty:
        return []
    out = df.copy()
    # Convert to object dtype first so that None placeholders survive (a plain
    # .where(..., None) on float64 columns coalesces back to NaN).
    out = out.astype(object).where(pd.notna(out), None)
    out = out.replace([np.inf, -np.inf], None)
    return out.to_dict(orient="records")


def jsonable_dict(rec: dict):
    """Convert a single dict to JSON-safe form (NaN/NaT/inf -> None)."""
    out = {}
    for k, v in rec.items():
        if v is None:
            out[k] = None
        elif isinstance(v, (dict, list)):
            out[k] = jsonable_dict(v) if isinstance(v, dict) else v
        else:
            try:
                is_nan = bool(pd.isna(v))
            except (TypeError, ValueError):
                is_nan = False
            try:
                is_inf = bool(v in (np.inf, -np.inf))
            except Exception:
                is_inf = False
            if is_nan or is_inf:
                out[k] = None
            else:
                out[k] = v
    return out