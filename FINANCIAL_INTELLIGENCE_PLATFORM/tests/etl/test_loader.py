import pathlib
import pandas as pd
import pytest

from src.etl.loader import read_canonical, validate_stock_prices, normalize_df
from src.etl.normaliser import normalize_year, normalize_ticker


def test_read_canonical_missing_returns_empty(tmp_path):
    df = read_canonical(tmp_path / "nope.xlsx")
    assert df.empty


def test_read_canonical_header1(tmp_path):
    # header=1 means row 0 is title, row 1 is real header
    path = tmp_path / "companies.xlsx"
    # write two-row header via openpyxl
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Title Row"])          # row 1 — skipped by header=1
    ws.append(["company_id", "company_name"])  # row 2 — real header
    ws.append(["TCS", "Tata Consultancy"])
    wb.save(path)
    df = read_canonical(path)
    assert list(df.columns) == ["company_id", "company_name"]
    assert len(df) == 1
    assert df.iloc[0]["company_id"] == "TCS"


def test_validate_stock_prices_ok():
    df = pd.DataFrame({
        "company_id": ["TCS"], "date": ["2024-03-31"], "close_price": [3500],
        "market_cap_crore": [1e6], "pe_ratio": [25], "pb_ratio": [12],
        "dividend_yield": [1.2],
    })
    assert validate_stock_prices(df) is True


def test_validate_stock_prices_empty_rejected():
    assert validate_stock_prices(pd.DataFrame()) is False


def test_validate_stock_prices_missing_cols_rejected():
    df = pd.DataFrame({"company_id": ["TCS"], "close_price": [100]})
    assert validate_stock_prices(df) is False


def test_validate_stock_prices_ohlcv_accepted():
    # The canonical stock_prices.xlsx is OHLCV (header on row 0); the loader accepts
    # OHLCV as long as company_id/date/close_price are present, then reduces to close_price.
    df = pd.DataFrame({
        "company_id": ["TCS"], "date": ["2024-03-31"],
        "open_price": [1], "high_price": [2], "low_price": [0.5],
        "close_price": [1.5], "volume": [100],
    })
    assert validate_stock_prices(df) is True


def test_validate_stock_prices_ohlcv_without_close_rejected():
    # OHLCV-like input without any close column must still be rejected
    df = pd.DataFrame({
        "company_id": ["TCS"], "date": ["2024-03-31"],
        "open_price": [1], "high_price": [2], "low_price": [0.5], "volume": [100],
    })
    assert validate_stock_prices(df) is False


def test_normalize_df_strips_and_normalizes_year():
    df = pd.DataFrame({
        " company_id ": ["  reliance  "],
        "Year": ["FY2020"],
        "sales": [100.0],
    })
    out = normalize_df(df, "profitandloss")
    assert "company_id" in out.columns
    assert out["company_id"].iloc[0] == "RELIANCE"
    assert out["year"].iloc[0] == "2020"


def test_normalize_df_drops_id_on_non_companies():
    df = pd.DataFrame({"id": [1], "company_id": ["TCS"], "year": [2020]})
    out = normalize_df(df, "profitandloss")
    assert "id" not in out.columns


def test_normalize_df_empty_passthrough():
    out = normalize_df(pd.DataFrame(), "companies")
    assert out.empty


def test_load_table_row_counts_from_source():
    """Loader reads correct row counts for core files when present."""
    root = pathlib.Path(".")
    # Prefer data/source, else project root prefixed files
    candidates = list(root.glob("data/source/companies.xlsx")) + list(root.glob("*companies.xlsx"))
    if not candidates:
        pytest.skip("companies.xlsx not available")
    df = read_canonical(candidates[0])
    assert not df.empty
    # 92 companies expected per sprint plan
    assert len(df) >= 90
    cols = {str(c).strip().lower() for c in df.columns}
    assert any("company" in c for c in cols)


def test_normalize_year_and_ticker_used_together():
    assert normalize_year("FY 2021") == "2021"
    assert normalize_ticker("  hdfc bank ") == "HDFCBANK"
