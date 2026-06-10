"""
agent_tools.py
"""
from __future__ import annotations
import json

import data_pipeline as dp
import risk_core as rc
import rag
import market_data as md


# ---------- การทำงานจริงของแต่ละเครื่องมือ ----------
def list_funds() -> dict:
    return {"funds": [{"fund_code": c, "fund_name": rc.FUND_NAMES.get(c, c)}
                      for c in dp.list_fund_codes()]}


def get_risk_metrics(fund_code: str) -> dict:
    return rc.risk_summary(fund_code)


def compare_funds(fund_codes: list[str]) -> dict:
    rows = [rc.risk_summary(c) for c in fund_codes]
    by_vol = sorted(rows, key=lambda x: x["annualized_volatility_pct"])
    by_sharpe = sorted(rows, key=lambda x: x["sharpe_ratio"], reverse=True)
    return {"table": rows,
            "lowest_risk": by_vol[0]["fund_code"],
            "highest_risk": by_vol[-1]["fund_code"],
            "best_risk_adjusted_return": by_sharpe[0]["fund_code"]}


def search_risk_policy(query: str) -> dict:
    """ค้นนโยบาย/ลิมิตความเสี่ยงจากเอกสาร (RAG) — ใช้ตอบเรื่องเกณฑ์/governance"""
    return {"policy_excerpts": rag.retrieve_policy(query, top_k=3)}


def data_quality_report() -> dict:
    """คืนรายงานการทำความสะอาดข้อมูล (โชว์ว่า clean อะไรไปบ้าง)"""
    return {"cleaning_steps": dp.get_cleaning_report()}


def get_live_price(fund_code: str) -> dict:
    """ราคา/NAV ณ ปัจจุบันแบบเรียลไทม์ของกองที่ระบุ"""
    return md.get_tick(fund_code)


DISPATCH = {
    "list_funds": list_funds,
    "get_risk_metrics": get_risk_metrics,
    "compare_funds": compare_funds,
    "search_risk_policy": search_risk_policy,
    "data_quality_report": data_quality_report,
    "get_live_price": get_live_price,
}


def run_tool(name: str, args: dict) -> str:
    """เรียกเครื่องมือตามชื่อ คืนผลเป็น JSON string"""
    if name not in DISPATCH:
        return json.dumps({"error": f"ไม่รู้จักเครื่องมือ {name}"}, ensure_ascii=False)
    try:
        return json.dumps(DISPATCH[name](**args), ensure_ascii=False)
    except Exception as e:  # noqa
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ---------- schema สำหรับ Anthropic Messages API (tool use) ----------
ANTHROPIC_TOOLS = [
    {
        "name": "list_funds",
        "description": "แสดงรายชื่อกองทุน/ดัชนีอ้างอิงทั้งหมดที่วิเคราะห์ได้ เรียกก่อนเสมอถ้าไม่แน่ใจรหัสกอง",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_risk_metrics",
        "description": "คำนวณตัวชี้วัดความเสี่ยงครบชุดของกองหนึ่ง: Volatility, VaR 95/99, Max Drawdown, Sharpe, ผลตอบแทน 1M/3M/YTD",
        "input_schema": {
            "type": "object",
            "properties": {"fund_code": {"type": "string", "description": "รหัสกอง เช่น ONE-EQ"}},
            "required": ["fund_code"],
        },
    },
    {
        "name": "compare_funds",
        "description": "เปรียบเทียบความเสี่ยงหลายกองพร้อมกัน เหมาะกับการเทียบกองกับ benchmark",
        "input_schema": {
            "type": "object",
            "properties": {"fund_codes": {"type": "array", "items": {"type": "string"},
                                          "description": "รายการรหัสกอง"}},
            "required": ["fund_codes"],
        },
    },
    {
        "name": "search_risk_policy",
        "description": "ค้นนโยบาย/ลิมิตความเสี่ยง/AI governance จากเอกสารนโยบาย (RAG) ใช้เมื่อต้องอ้างอิงเกณฑ์ เช่น 'VaR เกินลิมิตไหม'",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "คำถามเชิงนโยบาย"}},
            "required": ["query"],
        },
    },
    {
        "name": "data_quality_report",
        "description": "ดูรายงานการทำความสะอาดข้อมูล NAV ว่าตัด missing/ซ้ำ/outlier ไปเท่าไร",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_live_price",
        "description": "ดึงราคา/NAV ณ ปัจจุบันแบบเรียลไทม์ของกองที่ระบุ ใช้เมื่อผู้ใช้ถามราคาตอนนี้/ล่าสุด",
        "input_schema": {
            "type": "object",
            "properties": {"fund_code": {"type": "string", "description": "รหัสกอง"}},
            "required": ["fund_code"],
        },
    },
]
