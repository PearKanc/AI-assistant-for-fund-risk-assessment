"""
market_data.py
--------------
ชั้นดึงข้อมูล "เรียลไทม์" แบบสลับ provider ได้ (เลือกด้วย env MARKET_PROVIDER)

- simulated : สร้าง tick ใหม่ทุกครั้งที่เรียก (รันได้ทันที ไม่ต้องต่อเน็ต ใช้เดโม)
- yfinance  : ราคาจริงจากตลาด (บนเครื่องคุณ; map รหัสกอง -> ticker)

ในงานจริงเพิ่ม BloombergProvider / FactSetProvider ที่มี .get_tick() เหมือนกันได้เลย
ตัวอื่น ๆ ในระบบเรียกผ่าน get_tick() / get_live_series() โดยไม่ต้องรู้ว่ามาจาก provider ไหน
"""
from __future__ import annotations
import os
import time
import threading
import numpy as np
import pandas as pd

import data_pipeline as dp

PROVIDER = os.getenv("MARKET_PROVIDER", "simulated")

# map รหัสกอง -> ticker จริง (ใช้กับ yfinance) ปรับได้ตามจริง
TICKER_MAP = {
    "ONE-EQ": "^SET.BK",
    "ONE-GLOBAL": "ACWI",
    "ONE-BOND": "AGG",
    "SET-TRI": "^SET.BK",
}


class SimulatedLiveProvider:
    """random-walk จากราคาปิดล่าสุดในข้อมูลที่ clean แล้ว ให้ทุก poll เปลี่ยนเล็กน้อย"""
    def __init__(self):
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()
        self._rng = np.random.default_rng()

    def get_tick(self, fund_code: str) -> dict:
        with self._lock:
            if fund_code not in self._last:
                series = dp.get_nav_series(fund_code)
                self._last[fund_code] = float(series["nav"].iloc[-1])
            prev = self._last[fund_code]
            # ขยับแบบสุ่ม ~0.05% ต่อ tick
            new = prev * (1 + self._rng.normal(0, 0.0005))
            self._last[fund_code] = new
            return {
                "fund_code": fund_code,
                "price": round(new, 4),
                "change_pct": round((new / prev - 1) * 100, 4),
                "timestamp": pd.Timestamp.now().strftime("%H:%M:%S"),
                "source": "simulated",
            }


class YFinanceProvider:
    """ราคาจริงจาก Yahoo Finance (ต้อง pip install yfinance และมีอินเทอร์เน็ต)"""
    def __init__(self):
        import yfinance  # noqa  ตรวจว่าติดตั้งแล้ว
        self._prev: dict[str, float] = {}

    def get_tick(self, fund_code: str) -> dict:
        import yfinance as yf
        ticker = TICKER_MAP.get(fund_code, fund_code)
        data = yf.Ticker(ticker).history(period="1d", interval="1m")
        price = float(data["Close"].iloc[-1])
        prev = self._prev.get(fund_code, price)
        self._prev[fund_code] = price
        return {
            "fund_code": fund_code,
            "price": round(price, 4),
            "change_pct": round((price / prev - 1) * 100, 4) if prev else 0.0,
            "timestamp": pd.Timestamp.now().strftime("%H:%M:%S"),
            "source": f"yfinance:{ticker}",
        }


def _make_provider():
    if PROVIDER == "yfinance":
        try:
            return YFinanceProvider()
        except Exception as e:  # noqa
            print(f"[market] yfinance ใช้ไม่ได้ ({type(e).__name__}) -> ใช้ simulated")
    return SimulatedLiveProvider()


_PROVIDER = None


def get_provider():
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = _make_provider()
    return _PROVIDER


def get_tick(fund_code: str) -> dict:
    """ราคา ณ ปัจจุบันของกองที่ระบุ"""
    return get_provider().get_tick(fund_code)


def get_live_series(fund_code: str, extra_ticks: int = 0) -> pd.DataFrame:
    """
    time series ที่ใช้คำนวณความเสี่ยงแบบ live = ข้อมูลในอดีต (clean แล้ว)
    + ราคาล่าสุดจาก provider ต่อท้าย
    """
    hist = dp.get_nav_series(fund_code).copy()
    tick = get_tick(fund_code)
    live_row = pd.DataFrame([{"date": pd.Timestamp.now().normalize(), "nav": tick["price"]}])
    return pd.concat([hist, live_row], ignore_index=True)


if __name__ == "__main__":
    print(f"provider = {PROVIDER}")
    for _ in range(3):
        print(get_tick("ONE-EQ"))
        time.sleep(0.3)
