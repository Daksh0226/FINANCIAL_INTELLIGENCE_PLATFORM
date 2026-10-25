import pytest
from src.etl.normaliser import normalize_year, normalize_ticker

# 20 normalize_year tests
def test_year_YYYY():
    assert normalize_year("2020") == "2020"
def test_year_int():
    assert normalize_year(2021) == "2021"
def test_year_float_str():
    assert normalize_year("2020.0") == "2020"
def test_year_FY():
    assert normalize_year("FY2020") == "2020"
def test_year_FY_space():
    assert normalize_year("FY 2020") == "2020"
def test_year_FY_dash():
    assert normalize_year("FY-2020") == "2020"
def test_year_range_dash():
    assert normalize_year("2020-21") == "2020"
def test_year_range_slash():
    assert normalize_year("2020/21") == "2020"
def test_year_range_full():
    assert normalize_year("2020-2021") == "2020"
def test_year_Mar():
    assert normalize_year("Mar 2020") == "2020"
def test_year_March():
    assert normalize_year("March 2020") == "2020"
def test_year_Mar_dash():
    assert normalize_year("Mar-2020") == "2020"
def test_year_YYYY_MM():
    assert normalize_year("2020-03") == "2020-03"
def test_year_invalid():
    assert normalize_year("invalid") is None
def test_year_none():
    assert normalize_year(None) is None
def test_year_nan():
    import math; assert normalize_year(float("nan")) is None
def test_year_empty():
    assert normalize_year("") is None
def test_year_embedded():
    assert normalize_year("Year 2022 report") == "2022"
def test_year_Jan():
    assert normalize_year("Jan 2019") == "2019"
def test_year_Dec():
    assert normalize_year("Dec 2018") == "2018"

# 15 normalize_ticker tests
def test_ticker_simple():
    assert normalize_ticker("RELIANCE") == "RELIANCE"
def test_ticker_lower():
    assert normalize_ticker("reliance") == "RELIANCE"
def test_ticker_spaces():
    assert normalize_ticker("  TCS  ") == "TCS"
def test_ticker_inner_space():
    assert normalize_ticker("HDFC BANK") == "HDFCBANK"
def test_ticker_hyphen():
    assert normalize_ticker("M&M") == "MM"
def test_ticker_dot():
    assert normalize_ticker("BRK.B") == "BRK.B"
def test_ticker_underscore():
    assert normalize_ticker("ABC_DEF") == "ABC_DEF"
def test_ticker_numeric():
    assert normalize_ticker("123") == "123"
def test_ticker_empty():
    assert normalize_ticker("") is None
def test_ticker_none():
    assert normalize_ticker(None) is None
def test_ticker_nan():
    import math; assert normalize_ticker(float("nan")) is None
def test_ticker_special():
    assert normalize_ticker("A@B#C") == "ABC"
def test_ticker_mixed_case():
    assert normalize_ticker("hDfC") == "HDFC"
def test_ticker_with_numbers():
    assert normalize_ticker("TCS 123") == "TCS123"
def test_ticker_only_spaces():
    assert normalize_ticker("   ") is None
