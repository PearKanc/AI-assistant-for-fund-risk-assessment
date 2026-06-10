"""
make_raw_data.py
----------------
สร้างไฟล์ข้อมูลดิบ data/raw_nav.csv ที่ "เลอะ" แบบที่เจอจริงเวลารับข้อมูลจาก vendor
(มี missing, ค่าซ้ำ, NAV ติดลบ/ศูนย์, ตัวเลขเป็น string มี comma, วันสลับลำดับ, outlier)

รันครั้งเดียว: python make_raw_data.py
"""
from __future__ import annotations
import numpy as np
import pandas as pd

FUNDS = {
    "ONE-EQ":     (0.10, 0.22, 10.0),
    "ONE-GLOBAL": (0.12, 0.18, 10.0),
    "ONE-BOND":   (0.03, 0.04, 10.0),
    "SET-TRI":    (0.08, 0.20, 1000.0),
}
TRADING_DAYS = 252


def gbm(mu, sigma, nav0, days, rng):
    dt = 1 / TRADING_DAYS
    shocks = rng.normal((mu - 0.5 * sigma**2) * dt, sigma * np.sqrt(dt), days)
    return nav0 * np.exp(np.cumsum(shocks))


def build():
    rng = np.random.default_rng(7)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=500)
    rows = []
    for code, (mu, sigma, nav0) in FUNDS.items():
        nav = gbm(mu, sigma, nav0, len(dates), rng)
        for d, v in zip(dates, nav):
            rows.append({"fund_code": code, "date": d.strftime("%Y-%m-%d"), "nav": round(v, 4)})
    df = pd.DataFrame(rows)

    # ---- จงใจทำให้ "เลอะ" เลียนแบบข้อมูลจริง ----
    dirty = df.copy()

    # 1) ค่าว่าง (missing NAV) สุ่ม 1.5%
    miss_idx = rng.choice(dirty.index, size=int(len(dirty) * 0.015), replace=False)
    dirty.loc[miss_idx, "nav"] = np.nan

    # 2) NAV เป็น string มี comma (เช่น "1,053.20") บางแถว -> ทำให้คอลัมน์เป็น object
    str_idx = rng.choice(dirty.dropna(subset=["nav"]).index, size=40, replace=False)
    dirty["nav"] = dirty["nav"].astype(object)
    for i in str_idx:
        dirty.at[i, "nav"] = f"{float(dirty.at[i, 'nav']):,.2f}"

    # 3) NAV ติดลบ/ศูนย์ (error จากระบบต้นทาง)
    bad_idx = rng.choice(dirty.dropna(subset=["nav"]).index, size=8, replace=False)
    for i in bad_idx[:4]:
        dirty.at[i, "nav"] = 0.0
    for i in bad_idx[4:]:
        dirty.at[i, "nav"] = -abs(float(str(dirty.at[i, "nav"]).replace(",", "")))

    # 4) outlier spike (พิมพ์ผิด ทศนิยมหาย NAV x10)
    spike_idx = rng.choice(dirty.dropna(subset=["nav"]).index, size=5, replace=False)
    for i in spike_idx:
        try:
            dirty.at[i, "nav"] = float(str(dirty.at[i, "nav"]).replace(",", "")) * 10
        except ValueError:
            pass

    # 5) แถวซ้ำ (vendor ส่งซ้ำ)
    dup = dirty.sample(15, random_state=1)
    dirty = pd.concat([dirty, dup], ignore_index=True)

    # 6) สลับลำดับวัน (ไม่เรียง)
    dirty = dirty.sample(frac=1.0, random_state=2).reset_index(drop=True)

    dirty.to_csv("data/raw_nav.csv", index=False)
    print(f"เขียน data/raw_nav.csv แล้ว: {len(dirty)} แถว ({df['fund_code'].nunique()} กอง)")
    print("ปัญหาที่ใส่ไว้: missing, string+comma, ติดลบ/ศูนย์, outlier x10, ซ้ำ, ไม่เรียงวัน")


if __name__ == "__main__":
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    build()
