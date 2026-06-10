"""
data_pipeline.py
----------------
ETL จริงสำหรับข้อมูล NAV: โหลด CSV ดิบ -> ทำความสะอาด -> คืน time series ที่พร้อมใช้
ทุกขั้นตอนการ clean จะถูกบันทึกลง "cleaning report" เพื่อ traceability (สำคัญในงาน risk)

ในงานจริง: เปลี่ยนแค่ load_raw() ให้ไปดึง SQL / Bloomberg / FactSet แทนการอ่าน CSV
ส่วน clean_nav() ใช้ซ้ำได้เลย
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RAW_PATH = os.path.join(DATA_DIR, "raw_nav.csv")

# เกณฑ์ data quality
MAX_DAILY_MOVE = 0.30  # ผลตอบแทนรายวันเกิน ±30% ถือว่าผิดปกติ (น่าจะพิมพ์ผิด)


def load_raw(path: str = RAW_PATH) -> pd.DataFrame:
    """โหลดข้อมูลดิบ (จุดเดียวที่ต้องแก้เวลาเปลี่ยนไปต่อ DB/Bloomberg)"""
    return pd.read_csv(path, dtype={"nav": "object"})


def clean_nav(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    ทำความสะอาดข้อมูล NAV และคืน (df ที่สะอาด, report เป็นรายการบรรทัด)
    ขั้นตอน: parse ตัวเลข -> ตัดค่าผิด -> ตัดซ้ำ -> เรียงวัน -> ตัด outlier -> เติม gap
    """
    log: list[str] = []
    df = raw.copy()
    n0 = len(df)
    log.append(f"โหลดข้อมูลดิบ: {n0} แถว, {df['fund_code'].nunique()} กอง")

    # 1) แปลง nav ที่เป็น string มี comma -> ตัวเลข
    def to_num(x):
        if pd.isna(x):
            return np.nan
        return pd.to_numeric(str(x).replace(",", ""), errors="coerce")

    df["nav"] = df["nav"].map(to_num)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # 2) ตัดแถวที่ NAV ว่าง
    na = df["nav"].isna().sum()
    df = df.dropna(subset=["nav", "date"])
    log.append(f"ตัดแถว NAV/วันที่ว่าง: -{na} แถว")

    # 3) ตัด NAV <= 0 (เป็นไปไม่ได้)
    bad = (df["nav"] <= 0).sum()
    df = df[df["nav"] > 0]
    log.append(f"ตัด NAV ติดลบ/ศูนย์: -{bad} แถว")

    # 4) ตัดแถวซ้ำ (กอง+วันเดียวกัน)
    dup = df.duplicated(subset=["fund_code", "date"]).sum()
    df = df.drop_duplicates(subset=["fund_code", "date"], keep="last")
    log.append(f"ตัดแถวซ้ำ (กอง+วันที่): -{dup} แถว")

    # 5) เรียงวันต่อกอง
    df = df.sort_values(["fund_code", "date"]).reset_index(drop=True)
    log.append("เรียงข้อมูลตามกองและวันที่เรียบร้อย")

    # 6) ตัด outlier: ผลตอบแทนรายวันเกินเกณฑ์ -> ถือว่าพิมพ์ผิด ลบทิ้ง
    cleaned_parts = []
    out_total = 0
    for code, g in df.groupby("fund_code"):
        g = g.copy()
        g["ret"] = g["nav"].pct_change()
        mask = g["ret"].abs() > MAX_DAILY_MOVE
        out_total += int(mask.sum())
        g = g[~mask].drop(columns="ret")
        cleaned_parts.append(g)
    df = pd.concat(cleaned_parts, ignore_index=True)
    log.append(f"ตัด outlier (ผลตอบแทน/วัน > {MAX_DAILY_MOVE:.0%}): -{out_total} แถว")

    log.append(f"เหลือข้อมูลสะอาด: {len(df)} แถว (จาก {n0})")
    return df, log


# cache ไว้ในหน่วยความจำ เรียกซ้ำไม่ต้อง clean ใหม่
_CACHE: dict | None = None


def get_clean_data(force: bool = False) -> pd.DataFrame:
    global _CACHE
    if _CACHE is None or force:
        clean, log = clean_nav(load_raw())
        _CACHE = {"df": clean, "log": log}
    return _CACHE["df"]


def get_cleaning_report() -> list[str]:
    get_clean_data()
    return _CACHE["log"]  # type: ignore


def get_nav_series(fund_code: str) -> pd.DataFrame:
    """คืน time series (date, nav) ของกองที่ระบุ จากข้อมูลที่สะอาดแล้ว"""
    df = get_clean_data()
    out = df[df["fund_code"] == fund_code][["date", "nav"]].reset_index(drop=True)
    if out.empty:
        raise ValueError(f"ไม่พบข้อมูลกอง '{fund_code}'")
    return out


def list_fund_codes() -> list[str]:
    return sorted(get_clean_data()["fund_code"].unique().tolist())


if __name__ == "__main__":
    clean, report = clean_nav(load_raw())
    print("=== CLEANING REPORT ===")
    for line in report:
        print(" •", line)
    print("\n=== ตัวอย่างข้อมูลสะอาด ===")
    print(clean.groupby("fund_code")["nav"].agg(["count", "min", "max"]))
