import pandas as pd
from src.etl.validator import validate_all

def make_dfs(companies, pl=None, bs=None, cf=None, docs=None):
    dfs={}
    dfs["companies"]=companies
    if pl is not None: dfs["profitandloss"]=pl
    if bs is not None: dfs["balancesheet"]=bs
    if cf is not None: dfs["cashflow"]=cf
    if docs is not None: dfs["documents"]=docs
    return dfs

def test_dq01_duplicate_company():
    comps=pd.DataFrame([{"company_id":"TCS","company_name":"A"},{"company_id":"TCS","company_name":"B"}])
    f=validate_all(make_dfs(comps))
    assert any(f["rule_id"]=="DQ-01")

def test_dq02_duplicate_pl():
    comps=pd.DataFrame([{"company_id":"TCS","company_name":"A"}])
    pl=pd.DataFrame([{"company_id":"TCS","year":"2020","sales":100},{"company_id":"TCS","year":"2020","sales":100}])
    f=validate_all(make_dfs(comps, pl=pl))
    assert any(f["rule_id"]=="DQ-02")

def test_dq03_fk_violation():
    comps=pd.DataFrame([{"company_id":"TCS","company_name":"A"}])
    pl=pd.DataFrame([{"company_id":"UNKNOWN","year":"2020","sales":100}])
    f=validate_all(make_dfs(comps, pl=pl))
    assert any(f["rule_id"]=="DQ-03")

def test_dq04_bs_imbalance():
    comps=pd.DataFrame([{"company_id":"TCS","company_name":"A"}])
    bs=pd.DataFrame([{"company_id":"TCS","year":"2020","total_liabilities":100,"total_assets":200}])
    f=validate_all(make_dfs(comps, bs=bs))
    assert any(f["rule_id"]=="DQ-04")

def test_dq05_opm_mismatch():
    comps=pd.DataFrame([{"company_id":"TCS","company_name":"A"}])
    pl=pd.DataFrame([{"company_id":"TCS","year":"2020","sales":100,"operating_profit":10,"opm_percentage":50}])
    f=validate_all(make_dfs(comps, pl=pl))
    assert any(f["rule_id"]=="DQ-05")

def test_dq06_negative_sales():
    comps=pd.DataFrame([{"company_id":"TCS","company_name":"A"}])
    pl=pd.DataFrame([{"company_id":"TCS","year":"2020","sales":-100}])
    f=validate_all(make_dfs(comps, pl=pl))
    assert any(f["rule_id"]=="DQ-06")

def test_dq07_net_cash_mismatch():
    comps=pd.DataFrame([{"company_id":"TCS","company_name":"A"}])
    cf=pd.DataFrame([{"company_id":"TCS","year":"2020","operating_activity":100,"investing_activity":0,"financing_activity":0,"net_cash_flow":999}])
    f=validate_all(make_dfs(comps, cf=cf))
    assert any(f["rule_id"]=="DQ-07")

def test_dq08_tax_rate():
    comps=pd.DataFrame([{"company_id":"TCS","company_name":"A"}])
    pl=pd.DataFrame([{"company_id":"TCS","year":"2020","profit_before_tax":100,"tax":80}])
    f=validate_all(make_dfs(comps, pl=pl))
    assert any(f["rule_id"]=="DQ-08")

def test_dq09_dividend_cap():
    comps=pd.DataFrame([{"company_id":"TCS","company_name":"A"}])
    pl=pd.DataFrame([{"company_id":"TCS","year":"2020","dividend_payout_ratio":150}])
    f=validate_all(make_dfs(comps, pl=pl))
    assert any(f["rule_id"]=="DQ-09")

def test_dq10_url():
    comps=pd.DataFrame([{"company_id":"TCS","company_name":"A"}])
    docs=pd.DataFrame([{"company_id":"TCS","year":"2020","report_url":"ftp://bad.com"}])
    f=validate_all(make_dfs(comps, docs=docs))
    assert any(f["rule_id"]=="DQ-10")

def test_dq11_eps_sign():
    comps=pd.DataFrame([{"company_id":"TCS","company_name":"A"}])
    pl=pd.DataFrame([{"company_id":"TCS","year":"2020","eps":10,"net_profit":-100}])
    f=validate_all(make_dfs(comps, pl=pl))
    assert any(f["rule_id"]=="DQ-11")

def test_dq12_negative_borrow():
    comps=pd.DataFrame([{"company_id":"TCS","company_name":"A"}])
    bs=pd.DataFrame([{"company_id":"TCS","year":"2020","borrowings":-100}])
    f=validate_all(make_dfs(comps, bs=bs))
    assert any(f["rule_id"]=="DQ-12")

def test_dq13_low_year_coverage():
    comps=pd.DataFrame([{"company_id":"TCS","company_name":"A"}])
    pl=pd.DataFrame([{"company_id":"TCS","year":str(y),"sales":100} for y in range(2020,2023)])
    f=validate_all(make_dfs(comps, pl=pl))
    assert any(f["rule_id"]=="DQ-13")

def test_dq14_sales_yoy_spike():
    comps=pd.DataFrame([{"company_id":"TCS","company_name":"A"}])
    pl=pd.DataFrame([
        {"company_id":"TCS","year":"2020","sales":100},
        {"company_id":"TCS","year":"2021","sales":1000},
        {"company_id":"TCS","year":"2022","sales":1100},
        {"company_id":"TCS","year":"2023","sales":1200},
        {"company_id":"TCS","year":"2024","sales":1300},
    ])
    f=validate_all(make_dfs(comps, pl=pl))
    assert any(f["rule_id"]=="DQ-14")

def test_dq15_roe_outlier():
    comps=pd.DataFrame([{"company_id":"TCS","company_name":"A","roe_percentage":250}])
    f=validate_all(make_dfs(comps))
    assert any(f["rule_id"]=="DQ-15")

def test_dq16_missing_name():
    comps=pd.DataFrame([{"company_id":"TCS","company_name":None}])
    f=validate_all(make_dfs(comps))
    assert any(f["rule_id"]=="DQ-16")
