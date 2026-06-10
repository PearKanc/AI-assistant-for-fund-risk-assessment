"""
risk_core.py
------------
คำนวณ Risk Metrics จาก NAV time series ที่ "สะอาดแล้ว" (มาจาก data_pipeline)
ฟังก์ชันคำนวณแยกออกมาเพื่อ unit test ได้ และ LLM ไม่ต้องเดาตัวเลขเอง
"""
from __future__ import annotations
import numpy as np
import pandas as pd

import data_pipeline as dp

TRADING_DAYS = 252

FUND_NAMES = {
    "ONE-EQ": "ONE Thai Equity Fund",
    "ONE-GLOBAL": "ONE Global Equity Fund",
    "ONE-BOND": "ONE Fixed Income Fund",
    "SET-TRI": "SET Total Return Index (Benchmark)",
}


def _daily_returns(nav: pd.Series) -> pd.Series:
    return nav.pct_change().dropna()


def annualized_volatility(nav: pd.Series) -> float:
    return float(_daily_returns(nav).std(ddof=1) * np.sqrt(TRADING_DAYS))


def value_at_risk(nav: pd.Series, confidence: float = 0.95) -> float:
    """VaR รายวัน (historical) คืนเป็นบวก = ขาดทุนที่คาดว่าจะไม่เกินที่ระดับความเชื่อมั่น"""
    r = _daily_returns(nav)
    var = -np.percentile(r, (1 - confidence) * 100)
    return float(max(var, 0.0))


def max_drawdown(nav: pd.Series) -> float:
    dd = nav / nav.cummax() - 1.0
    return float(-dd.min())


def sharpe_ratio(nav: pd.Series, risk_free: float = 0.02) -> float:
    excess = _daily_returns(nav).mean() * TRADING_DAYS - risk_free
    vol = annualized_volatility(nav)
    return float(excess / vol) if vol > 0 else float("nan")


def period_return(nav: pd.Series, days: int) -> float:
    if len(nav) <= days:
        days = len(nav) - 1
    return float(nav.iloc[-1] / nav.iloc[-1 - days] - 1.0)


def risk_summary(fund_code: str) -> dict:
    df = dp.get_nav_series(fund_code)
    nav = df["nav"]
    return {
        "fund_code": fund_code,
        "fund_name": FUND_NAMES.get(fund_code, fund_code),
        "as_of": df["date"].iloc[-1].strftime("%Y-%m-%d"),
        "latest_nav": round(float(nav.iloc[-1]), 4),
        "observations": int(len(nav)),
        "annualized_volatility_pct": round(annualized_volatility(nav) * 100, 2),
        "VaR_95_daily_pct": round(value_at_risk(nav, 0.95) * 100, 2),
        "VaR_99_daily_pct": round(value_at_risk(nav, 0.99) * 100, 2),
        "max_drawdown_pct": round(max_drawdown(nav) * 100, 2),
        "sharpe_ratio": round(sharpe_ratio(nav), 2),
        "return_1m_pct": round(period_return(nav, 21) * 100, 2),
        "return_3m_pct": round(period_return(nav, 63) * 100, 2),
        "return_ytd_pct": round(period_return(nav, 252) * 100, 2),
    }


if __name__ == "__main__":
    import json
    for c in dp.list_fund_codes():
        print(json.dumps(risk_summary(c), ensure_ascii=False))
