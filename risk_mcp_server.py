"""
risk_mcp_server.py
------------------
MCP Server (FastMCP) — ทางเลือกเชื่อมกับ Claude Desktop / Cursor
ใช้ logic เดียวกับ chatbot (agent_tools) เพื่อให้ผลตรงกันทุกช่องทาง

รัน: python risk_mcp_server.py
config Claude Desktop ดูใน README
"""
from __future__ import annotations
from fastmcp import FastMCP

import agent_tools as t

mcp = FastMCP("ONE-RiskMCP 🛡️")


@mcp.tool
def list_funds() -> dict:
    """แสดงรายชื่อกองทุน/ดัชนีอ้างอิงทั้งหมดที่วิเคราะห์ได้"""
    return t.list_funds()


@mcp.tool
def get_risk_metrics(fund_code: str) -> dict:
    """ตัวชี้วัดความเสี่ยงครบชุดของกองหนึ่ง: Volatility, VaR 95/99, Max Drawdown, Sharpe, ผลตอบแทน"""
    return t.get_risk_metrics(fund_code)


@mcp.tool
def compare_funds(fund_codes: list[str]) -> dict:
    """เปรียบเทียบความเสี่ยงหลายกองพร้อมกัน ระบุกองเสี่ยงสุด/ต่ำสุด/Sharpe ดีสุด"""
    return t.compare_funds(fund_codes)


@mcp.tool
def search_risk_policy(query: str) -> dict:
    """ค้นนโยบาย/ลิมิตความเสี่ยง/AI governance จากเอกสาร (RAG)"""
    return t.search_risk_policy(query)


@mcp.tool
def data_quality_report() -> dict:
    """รายงานการทำความสะอาดข้อมูล NAV (ตัด missing/ซ้ำ/outlier ไปเท่าไร)"""
    return t.data_quality_report()


@mcp.tool
def get_live_price(fund_code: str) -> dict:
    """ราคา/NAV ณ ปัจจุบันแบบเรียลไทม์ของกองที่ระบุ"""
    return t.get_live_price(fund_code)


if __name__ == "__main__":
    mcp.run()
