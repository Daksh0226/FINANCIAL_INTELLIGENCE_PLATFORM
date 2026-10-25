PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- 10 tables: companies, profitandloss, balancesheet, cashflow, analysis, documents, prosandcons, sectors, stock_prices, financial_ratios + peer_groups + peer_percentiles auxiliary
DROP TABLE IF EXISTS peer_percentiles;
DROP TABLE IF EXISTS financial_ratios;
DROP TABLE IF EXISTS stock_prices;
DROP TABLE IF EXISTS peer_groups;
DROP TABLE IF EXISTS financial_ratios;
DROP TABLE IF EXISTS prosandcons;
DROP TABLE IF EXISTS documents;
DROP TABLE IF EXISTS analysis;
DROP TABLE IF EXISTS cashflow;
DROP TABLE IF EXISTS balancesheet;
DROP TABLE IF EXISTS profitandloss;
DROP TABLE IF EXISTS sectors;
DROP TABLE IF EXISTS companies;

CREATE TABLE companies (
    company_id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    broad_sector TEXT,
    sub_sector TEXT,
    market_cap_category TEXT,
    nse_ticker TEXT,
    bse_ticker TEXT,
    roe_percentage REAL,
    roce_percentage REAL,
    about TEXT
);

CREATE TABLE sectors (
    sector_id INTEGER PRIMARY KEY AUTOINCREMENT,
    broad_sector TEXT UNIQUE NOT NULL,
    company_count INTEGER,
    median_roe REAL,
    median_pe REAL,
    median_de REAL
);

CREATE TABLE profitandloss (
    company_id TEXT NOT NULL,
    year TEXT NOT NULL,
    sales REAL,
    operating_profit REAL,
    opm_percentage REAL,
    other_income REAL,
    interest REAL,
    depreciation REAL,
    profit_before_tax REAL,
    tax REAL,
    net_profit REAL,
    eps REAL,
    dividend_payout_ratio REAL,
    PRIMARY KEY (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
);

CREATE TABLE balancesheet (
    company_id TEXT NOT NULL,
    year TEXT NOT NULL,
    equity_capital REAL,
    reserves REAL,
    borrowings REAL,
    other_liabilities REAL,
    total_liabilities REAL,
    fixed_assets REAL,
    investments REAL,
    other_assets REAL,
    total_assets REAL,
    PRIMARY KEY (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
);

CREATE TABLE cashflow (
    company_id TEXT NOT NULL,
    year TEXT NOT NULL,
    operating_activity REAL,
    investing_activity REAL,
    financing_activity REAL,
    net_cash_flow REAL,
    PRIMARY KEY (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
);

-- analysis is one row per (company, reporting period), not one row per company.
-- The period label is carried inside the metric strings (e.g. "10 Years: 21%", "TTM: 5%"),
-- so the source "id" is preserved as analysis_id to give each period row a stable key.
CREATE TABLE analysis (
    analysis_id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    compounded_sales_growth TEXT,
    compounded_profit_growth TEXT,
    stock_price_cagr TEXT,
    roe TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
);

CREATE TABLE documents (
    company_id TEXT NOT NULL,
    year TEXT NOT NULL,
    report_url TEXT,
    PRIMARY KEY (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
);

CREATE TABLE prosandcons (
    company_id TEXT NOT NULL,
    type TEXT NOT NULL,
    description TEXT,
    PRIMARY KEY (company_id, type, description),
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
);

CREATE TABLE peer_groups (
    peer_group_name TEXT NOT NULL,
    company_id TEXT NOT NULL,
    is_benchmark INTEGER DEFAULT 0,
    PRIMARY KEY (peer_group_name, company_id),
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
);

CREATE TABLE stock_prices (
    company_id TEXT NOT NULL,
    date TEXT NOT NULL,
    close_price REAL,
    market_cap_crore REAL,
    pe_ratio REAL,
    pb_ratio REAL,
    dividend_yield REAL,
    PRIMARY KEY (company_id, date),
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
);

CREATE TABLE financial_ratios (
    company_id TEXT NOT NULL,
    year TEXT NOT NULL,
    net_profit_margin_pct REAL,
    operating_profit_margin_pct REAL,
    return_on_equity_pct REAL,
    return_on_capital_employed_pct REAL,
    return_on_assets_pct REAL,
    debt_to_equity REAL,
    interest_coverage REAL,
    icr_label TEXT,
    high_leverage_flag INTEGER DEFAULT 0,
    icr_warning_flag INTEGER DEFAULT 0,
    net_debt_cr REAL,
    asset_turnover REAL,
    free_cash_flow_cr REAL,
    capex_cr REAL,
    capex_intensity_pct REAL,
    fcf_conversion_pct REAL,
    earnings_per_share REAL,
    book_value_per_share REAL,
    dividend_payout_ratio_pct REAL,
    total_debt_cr REAL,
    cash_from_operations_cr REAL,
    revenue_cagr_3yr REAL,
    revenue_cagr_5yr REAL,
    revenue_cagr_10yr REAL,
    pat_cagr_3yr REAL,
    pat_cagr_5yr REAL,
    pat_cagr_10yr REAL,
    eps_cagr_3yr REAL,
    eps_cagr_5yr REAL,
    eps_cagr_10yr REAL,
    fcf_cagr_3yr REAL,
    fcf_cagr_5yr REAL,
    fcf_cagr_10yr REAL,
    revenue_cagr_5yr_flag TEXT,
    pat_cagr_5yr_flag TEXT,
    eps_cagr_5yr_flag TEXT,
    fcf_cagr_3yr_flag TEXT,
    fcf_cagr_5yr_flag TEXT,
    fcf_cagr_10yr_flag TEXT,
    cfo_quality_score REAL,
    cfo_quality_label TEXT,
    composite_quality_score REAL,
    sector_relative_score REAL,
    PRIMARY KEY (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
);

CREATE TABLE peer_percentiles (
    company_id TEXT NOT NULL,
    peer_group_name TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL,
    percentile_rank REAL,
    year TEXT NOT NULL,
    PRIMARY KEY (company_id, peer_group_name, metric, year),
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
);

CREATE INDEX idx_pl_company_year ON profitandloss(company_id, year);
CREATE INDEX idx_bs_company_year ON balancesheet(company_id, year);
CREATE INDEX idx_cf_company_year ON cashflow(company_id, year);
CREATE INDEX idx_fr_company_year ON financial_ratios(company_id, year);
CREATE INDEX idx_sp_company_date ON stock_prices(company_id, date);
CREATE INDEX idx_analysis_company ON analysis(company_id);
