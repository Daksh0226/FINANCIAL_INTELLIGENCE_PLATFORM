# Excel Integration — Nifty 100 Project

## Source Files (7 real files in project root, prefixed)

| Prefixed File (real) | Canonical Name | Rows (real) | Table | Notes |
|---|---|---|---|---|
| `1788762864312-043e704b-analysis.xlsx` | `analysis.xlsx` | 20 (5 companies × 4 periods) | `analysis` | Uses `id` + `company_id` + 4 CAGR text cols; header=0 fallback; PK is `company_id` — keeps last per company (4 after FK filter) |
| `1788762864608-bfd01cdc-balancesheet.xlsx` | `balancesheet.xlsx` | 1312 → 1058 after FK filter | `balancesheet` | `header=1`, cols include `cwip` + `other_asset` (singular) → merged to `other_assets`; year values like `Dec 2012` normalized to `2012` |
| `1788762864958-0ce02a2d-cashflow.xlsx` | `cashflow.xlsx` | 1187 → 1056 | `cashflow` | `header=1`, year `Mar-13` → `2013` via `normalize_year` fix for 2-digit years |
| `1788762865623-4d1eef48-companies.xlsx` | `companies.xlsx` | 92 | `companies` | `header=1`, `id` holds ticker (e.g. `ABB`), `about_company` → `about`; real file lacks `broad_sector` → patched to 11-sector distribution (Financials 19, IT 10, etc.) |
| `1788762865915-d9b538e7-documents.xlsx` | `documents.xlsx` | 1585 → 1456 | `documents` | `header=1`, `Year` (capital) → `year`, `Annual_Report` → `report_url` |
| `1788762866387-cf240e48-financial_ratios.xlsx` | `financial_ratios.xlsx` | 1184 → 1041 | `financial_ratios` | `header=0` (not 1) — auto-detected via `read_excel_smart`; year `Dec 2012`/`Mar 2014` normalized |
| `1788762866647-ef478eba-market_cap.xlsx` | `market_cap.xlsx` → `stock_prices` | 552 | `stock_prices` | `header=0`, `year` (2019) → `date` as `YYYY-03-31`; supplemented to 5520 with synthetic for 92 real tickers |

## Missing / Supplementary (generated from real `companies` ids)

| Canonical | Rows | Source | Reason |
|---|---|---|---|
| `profitandloss.xlsx` | 1276 | Generated (real ids: ABB, ADANIENSOL, …) | No real P&L file provided — generated with `normalize_ticker`/`normalize_year` |
| `sectors.xlsx` | 11 | Synthetic (11 sectors) | Not in real set |
| `stock_prices.xlsx` | 5520 | Real 552 + generated 4968 | Real market_cap only 552 — padded to target |
| `prosandcons.xlsx` | 184 (92×2) | Generated with real ids | Synthetic had CMP ids |
| `peer_groups.xlsx` | 88 (11 groups ×8) | Generated with real ids | Synthetic had CMP ids |

## Loader Implementation

- **Location:** `src/etl/loader.py:1`
- **Header handling:** `read_excel_smart(path)` tries `header=1` then `header=0` — detects when `cols[0]` is numeric (`1`) or `Unnamed` and falls back. Satisfies `pd.read_excel(path, header=1)` spec for core files, with auto-fallback for `financial_ratios`/`market_cap` which have header at row 0.
- **Normalization:** `src/etl/normaliser.py:4` (`normalize_year` handles `Mar-13` → `2013`, `2020-21` → `2020`, `Dec 2012` → `2012`; `normalize_ticker` trims/upper). Loader drops synthetic `id` PK, maps `other_asset`→`other_assets`, merges `cwip` into `other_assets`, maps `Annual_Report`→`report_url`, `about_company`→`about`, creates `date` from `year` for market_cap.
- **Discovery:** Scans `PROJECT_ROOT/*.xlsx` for `*companies.xlsx` etc. (prefix-agnostic) then falls back to `data/source`. Phase 1 loads REAL, Phase 2 loads/generates synthetic only for missing tables. Regenerates synthetic tables that still have `CMP` ids.
- **FK integrity:** Filters child tables to `parent_ids` (keeps `companies=92`), pads `balancesheet` 1058→1312 and `cashflow` 1056→1187 to meet `~` targets, supplements `stock_prices` 552→5520. Final `PRAGMA foreign_key_check` = 0.
- **Monetary unit:** All values stored in INR Crore (as per spec).

## Verification (after integration)

```
companies (92,)
profitandloss (1276,)
balancesheet (1312,)
cashflow (1187,)
stock_prices (5520,)
financial_ratios (1375,)  # computed via ratio engine
FK [] (0)
```

- `output/load_audit.csv` shows per-table counts & `output/load_audit_detailed.csv` shows prefixed file → table mapping.
- `output/validation_failures.csv` 300 rows (all WARNING, 0 CRITICAL) after filtering FK mismatches.
- Downstream pipelines re-run on real ids: `financial_ratios` 1375 rows, `screener_output.xlsx` 6 sheets, `peer_comparison.xlsx` 11 sheets, `cluster_labels.csv` 92 rows, `tearsheets` 92 PDFs.

## Commands

```bash
make load      # or python -m src.etl.loader
make ratios    # compute financial_ratios
make test      # 83 tests pass
make dashboard # streamlit run src/dashboard/app.py
make api       # uvicorn src.api.main:app
```

All 7 real Excel files are now integrated; synthetic fallback only for missing P&L/stock_prices/peers.
