# Nifty 100 Financial Intelligence Platform

A comprehensive financial analytics platform for India's Nifty 100 companies covering 14 fiscal years (2011–2024) plus TTM data.

## Overview

This platform helps analyze, screen, and visualize financial data for Nifty 100 companies with tools for ratio analysis, peer comparisons, stock screening, and AI-powered insights.

**Key Stats:**
- **100** canonical companies across **10** sectors
- **14 fiscal years** (2011–2024) + TTM
- **43 financial ratios** calculated per company per year
- **12 data sources** loaded into SQLite database
- **27 REST API endpoints**
- **8 interactive dashboard pages**
- **147 automated tests**

## Features

| Feature | Description |
|---------|-------------|
| **Data Pipeline** | ETL process loads Excel files into SQLite with data quality validation |
| **Financial Ratios** | Calculates 43 KPIs (profitability, leverage, growth, cash flow, valuation) |
| **Stock Screener** | 6 preset strategies + 23 customizable metrics with Excel export |
| **Peer Comparison** | Compare companies within peer groups with percentile rankings and radar charts |
| **Interactive Dashboard** | 8 Streamlit pages for exploration and analysis |
| **REST API** | FastAPI backend with 27 endpoints for programmatic access |
| **PDF Reports** | Generate company tearsheets, sector reports, and portfolio summaries |
| **AI Insights** | Automated pros/cons generation from financial statement analysis |
| **Company Clustering** | K-Means clustering to identify company archetypes |

## Tech Stack

- **Data Processing**: Python, pandas, openpyxl
- **Database**: SQLite
- **Backend API**: FastAPI, Uvicorn
- **Dashboard**: Streamlit
- **Analytics**: scikit-learn (clustering), numpy
- **Reporting**: ReportLab (PDF generation)
- **Testing**: pytest

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Windows, macOS, or Linux

### Installation

1. **Navigate to the project directory**
   ```bash
   cd FINANCIAL_INTELLIGENCE_PLATFORM
   ```

2. **Create and activate virtual environment**
   
   **Windows:**
   ```cmd
   python -m venv venv
   venv\Scripts\activate
   ```
   
   **macOS/Linux:**
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Load data into database**
   ```bash
   python -m src.etl.loader
   ```
   This reads Excel files from `data/source/` and creates `data/nifty100.db`. Takes ~30 seconds.

5. **Calculate financial ratios**
   ```bash
   python -m src.analytics.ratios
   python -m src.analytics.cagr
   python -m src.analytics.cashflow_kpis
   ```
   Takes ~15 seconds. Or run all at once with `make load && make ratios`.

## Running the Application

The platform runs as two services: a Streamlit dashboard and a FastAPI server.

### Option 1: Quick start (Windows)
```cmd
start_servers.bat
```

### Option 2: Using Make
```bash
make dashboard  # Start Streamlit on port 8501
make api        # Start FastAPI on port 8000
```
Run in separate terminals.

### Option 3: Manual start
```bash
# Terminal 1 - Dashboard
streamlit run src/dashboard/app.py --server.port 8501

# Terminal 2 - API
uvicorn src.api.main:app --port 8000 --reload
```

### Access Points

- **Dashboard**: [http://localhost:8501](http://localhost:8501)
- **API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Documentation (ReDoc)**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Project Structure

```
FINANCIAL_INTELLIGENCE_PLATFORM/
├── config/           # Configuration files (screener settings)
├── data/             # Database and source Excel files
│   ├── nifty100.db   # SQLite database
│   └── source/       # Input Excel workbooks
├── db/               # Database schema
├── docs/             # Documentation and API specs
├── output/           # Generated reports and exports
├── reports/          # PDF reports and charts
├── src/              # Source code
│   ├── api/          # FastAPI REST API
│   ├── analytics/    # Ratio calculations, CAGR, clustering
│   ├── dashboard/    # Streamlit dashboard app
│   ├── etl/          # Data extraction, transformation, loading
│   ├── nlp/          # Text analysis for pros/cons
│   ├── reports/      # PDF report generation
│   └── screener/     # Stock screening engine
├── tests/            # Test suite (147 tests)
├── Makefile          # Convenient commands
├── requirements.txt  # Python dependencies
└── start_servers.bat # Windows launcher
```

## Configuration

Settings can be configured in:
- `.env` - Database path, ports, environment
- `.streamlit/config.toml` - Dashboard theme and server settings
- `config/screener_config.yaml` - Screener presets and metrics

## Testing

Run the test suite:
```bash
pytest
```

Or with more verbose output:
```bash
pytest -v
```

## Data Sources

The platform uses 12 Excel workbooks in `data/source/`:
- Company information, sectors, peer groups
- Financial statements (P&L, Balance Sheet, Cash Flow)
- Financial ratios and market data
- Stock prices, analysis data, documents, and pros/cons

## Notes

- The database (`data/nifty100.db`) is pre-loaded and ready to use
- The dashboard includes 8 pages: Overview, Company Analysis, Peer Comparison, Screener, Clustering, Reports, API Explorer, and Data Quality
- For LAN access, the dashboard binds to `0.0.0.0` by default
- API has CORS enabled for dashboard communication
