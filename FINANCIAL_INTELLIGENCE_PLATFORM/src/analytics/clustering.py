"""Clustering: KMeans k=5, StandardScaler, sector median impute, plots, reports."""
import pathlib, sqlite3
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

DB_PATH = pathlib.Path("data/nifty100.db")
OUTPUT_DIR = pathlib.Path("output")

FEATURES = ["return_on_equity_pct","debt_to_equity","revenue_cagr_5yr","operating_profit_margin_pct","free_cash_flow_cr"]
# Note: spec says fcf_cagr_5yr but not available as column; use free_cash_flow_cr as proxy and compute fcf_cagr_5yr if needed

def run_clustering(db_path=DB_PATH, k=5):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    companies = pd.read_sql("SELECT company_id, broad_sector FROM companies", con)
    sector_map = dict(zip(companies.company_id, companies.broad_sector))
    fr = pd.read_sql("SELECT * FROM financial_ratios", con)
    # use latest year per company
    fr["year_int"] = pd.to_numeric(fr["year"], errors="coerce")
    latest = fr.sort_values("year_int").groupby("company_id").tail(1)
    # ensure all 92 companies present
    latest = pd.merge(companies[["company_id","broad_sector"]], latest, on="company_id", how="left")

    # sector median impute
    for f in FEATURES:
        if f not in latest.columns:
            latest[f] = np.nan
        # compute sector median
        medians = latest.groupby("broad_sector")[f].median()
        for idx, row in latest.iterrows():
            if pd.isna(row[f]):
                sec = row["broad_sector"]
                median_val = medians.get(sec, np.nan)
                if pd.isna(median_val):
                    median_val = latest[f].median()
                latest.at[idx, f] = median_val if pd.notna(median_val) else 0
        # still NaN -> fill 0
        latest[f] = latest[f].fillna(0)

    X = latest[FEATURES].values
    # winsorise not needed for clustering, but ensure finite
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    # elbow plot for k=1..8
    inertias = []
    ks = range(1,9)
    for kk in ks:
        km = KMeans(n_clusters=kk, random_state=42, n_init=10)
        km.fit(Xs)
        inertias.append(km.inertia_)
    plt.figure(figsize=(6,4))
    plt.plot(list(ks), inertias, marker="o")
    plt.title("Elbow Plot (k vs inertia)")
    plt.xlabel("k")
    plt.ylabel("Inertia")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "elbow_plot.png", dpi=150)
    plt.close()

    # final k=5
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(Xs)
    latest["cluster"] = labels

    # correlation heatmap
    corr = latest[FEATURES].corr()
    plt.figure(figsize=(7,5))
    sns.heatmap(corr, annot=True, cmap="coolwarm", fmt=".2f")
    plt.title("Feature Correlation Heatmap")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "correlation_heatmap.png", dpi=150)
    plt.close()

    # distance to centroid for cluster_labels
    dist_to_centroid = np.linalg.norm(Xs - kmeans.cluster_centers_[labels], axis=1)
    latest["distance_to_centroid"] = dist_to_centroid
    latest["distance_from_centroid"] = dist_to_centroid

    # outlier_report: Z-score per metric per broad_sector >3 per spec
    # Compute Z-score for each metric per broad_sector — flag companies where any metric has absolute Z-score >3
    outlier_rows = []
    for metric in FEATURES:
        # Use latest before scaling for Z-score interpretation
        grp = latest.groupby("broad_sector")[metric]
        means = grp.transform("mean")
        stds = grp.transform("std")
        # avoid division by zero
        z = (latest[metric] - means) / stds.replace(0, np.nan)
        flagged = latest[z.abs() > 3]
        for _, r in flagged.iterrows():
            outlier_rows.append({"company_id": r["company_id"], "broad_sector": r["broad_sector"], "metric": metric, "value": r[metric], "z_score": float(z.loc[r.name]) if pd.notna(z.loc[r.name]) else None, "cluster": int(r["cluster"])})
    # also include distance outliers > mean+2std as supplemental
    threshold = dist_to_centroid.mean() + 2*dist_to_centroid.std()
    dist_outliers = latest[dist_to_centroid > threshold]
    for _, r in dist_outliers.iterrows():
        # avoid duplicate
        if not any(o["company_id"]==r["company_id"] and o["metric"]=="distance_to_centroid" for o in outlier_rows):
            outlier_rows.append({"company_id": r["company_id"], "broad_sector": r["broad_sector"], "metric": "distance_to_centroid", "value": float(r["distance_to_centroid"]), "z_score": None, "cluster": int(r["cluster"])})
    # deduplicate
    outlier_df = pd.DataFrame(outlier_rows).drop_duplicates(subset=["company_id","metric"]) if outlier_rows else pd.DataFrame(columns=["company_id","broad_sector","metric","value","z_score","cluster"])
    # spec expects at least company_id, metric, value, z - keep compatible columns
    if outlier_df.empty:
        # create empty with header
        outlier_df = pd.DataFrame(columns=["company_id","broad_sector","metric","value","z_score","cluster","distance_to_centroid"])
    outlier_df.to_csv(OUTPUT_DIR / "outlier_report.csv", index=False)

    # cluster profiling with descriptive names
    # Assign names based on financial profiles: High-Quality Compounders, Defensive Dividend Payers, Value Cyclicals, Distressed/Turnaround, Emerging Growth
    # Profile each cluster: compute mean of features
    profile = latest.groupby("cluster")[FEATURES].mean()
    # Simple heuristic to name clusters
    cluster_names = {}
    # rank clusters by ROE and debt
    # We'll assign names deterministically for reproducibility: sort by avg ROE descending
    sorted_clusters = profile.sort_values("return_on_equity_pct", ascending=False).index.tolist()
    name_pool = ["High-Quality Compounders", "Emerging Growth", "Defensive Dividend Payers", "Value Cyclicals", "Distressed or Turnaround"]
    for i, cl in enumerate(sorted_clusters):
        cluster_names[cl] = name_pool[i % len(name_pool)]
    latest["cluster_name"] = latest["cluster"].map(cluster_names)
    latest["cluster_id"] = latest["cluster"]

    # portfolio_stats: P10, P25, P50, P75, P90, Mean, Std for each KPI across all 92 companies (latest year)
    kpis_for_stats = ["return_on_equity_pct","return_on_capital_employed_pct","debt_to_equity","net_profit_margin_pct","asset_turnover","fcf_conversion_pct","revenue_cagr_5yr","pat_cagr_5yr","eps_cagr_5yr","interest_coverage"]
    # ensure those columns exist
    stats_rows = []
    for kpi in kpis_for_stats:
        if kpi not in latest.columns:
            continue
        vals = latest[kpi].dropna()
        if vals.empty:
            continue
        stats_rows.append({
            "kpi": kpi,
            "P10": float(vals.quantile(0.10)),
            "P25": float(vals.quantile(0.25)),
            "P50": float(vals.quantile(0.50)),
            "P75": float(vals.quantile(0.75)),
            "P90": float(vals.quantile(0.90)),
            "Mean": float(vals.mean()),
            "Std": float(vals.std()),
            "Min": float(vals.min()),
            "Max": float(vals.max()),
            "Count": int(vals.count())
        })
    stats_df = pd.DataFrame(stats_rows)
    stats_df.to_csv(OUTPUT_DIR / "portfolio_stats.csv", index=False)
    # also save cluster profile for reference
    try:
        profile.to_csv(OUTPUT_DIR / "cluster_profile.csv", index=True)
    except Exception:
        pass

    # cluster_labels.csv with 92 rows per spec: company_id, cluster_id (0-4), cluster_name, distance_from_centroid (+ broad_sector for convenience)
    out_labels = latest[["company_id","cluster_id","cluster_name","distance_from_centroid","broad_sector","cluster"]].rename(columns={"cluster":"cluster"})
    # ensure order 0-4 naming consistent
    out_labels.to_csv(OUTPUT_DIR / "cluster_labels.csv", index=False)

    con.close()
    return latest

if __name__ == "__main__":
    df = run_clustering()
    print(f"Clustering done: {df['cluster'].nunique()} clusters, {len(df)} rows")
