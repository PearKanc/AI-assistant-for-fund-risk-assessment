"""
chatbot_app.py  —  ONE Risk Copilot Dashboard
----------------------------------------------
Dashboard สว่าง อ่านง่าย รวมทุกอย่างในหน้าเดียว:
  - การ์ดตัวชี้วัดความเสี่ยง (VaR, Volatility, Drawdown, Sharpe)
  - ราคาสด real-time (auto-refresh)
  - กราฟ NAV และ Drawdown
  - แชทกับ AI (agentic: Claude เลือกเรียกเครื่องมือเอง + RAG)

รัน:
    export ANTHROPIC_API_KEY=sk-ant-...
    streamlit run chatbot_app.py
"""
from __future__ import annotations
import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import anthropic

import agent_tools as t
import data_pipeline as dp
import risk_core as rc
import market_data as md
import guardrail
import llm_client

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = (
    "คุณคือผู้ช่วยนักวิเคราะห์ความเสี่ยงกองทุนของ บลจ. "
    "ถามเรื่องตัวเลข (VaR, drawdown, ผลตอบแทน) ให้เรียกเครื่องมือคำนวณเสมอ ห้ามเดาเอง "
    "ถามเรื่องเกณฑ์/ลิมิต/นโยบาย/governance ให้เรียก search_risk_policy "
    "ถามราคาตอนนี้ให้เรียก get_live_price "
    "ถ้าถามว่ากองเกินลิมิตไหม ให้คำนวณก่อนแล้วค้นนโยบายมาเทียบ "
    "ตอบเฉพาะเรื่องกองทุน/การลงทุน/การบริหารความเสี่ยง คำถามนอกเรื่องให้ปฏิเสธสั้น ๆ "
    "ตอบภาษาไทยกระชับ เหมาะเสนอผู้บริหาร อ้างอิงตัวเลข/นโยบายที่ได้จากเครื่องมือ"
)

st.set_page_config(page_title="ONE Risk Copilot", page_icon="🛡️", layout="wide")

# ---------- ธีมสว่าง อ่านง่าย ----------
st.markdown("""
<style>
.stApp { background: #f6f8fc; }
.block-container { padding-top: 2rem; }
div[data-testid="stMetric"] {
  background: #ffffff; border: 1px solid #e3e8f0; border-radius: 14px;
  padding: 16px 18px; box-shadow: 0 1px 3px rgba(16,24,40,.06);
}
div[data-testid="stMetricLabel"] { color:#475467; font-weight:500; }
h1,h2,h3 { color:#101828; }
.badge { display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px; font-weight:600; }
.ok  { background:#e7f6ec; color:#067647; }
.warn{ background:#fef0e6; color:#b54708; }
</style>
""", unsafe_allow_html=True)

FUNDS = dp.list_fund_codes()

# ---------- Sidebar ----------
with st.sidebar:
    st.title("🛡️ ONE Risk Copilot")
    st.caption("Dashboard บริหารความเสี่ยงกองทุน + AI")
    fund = st.selectbox("เลือกกองทุน", FUNDS, index=FUNDS.index("ONE-EQ") if "ONE-EQ" in FUNDS else 0)
    live_on = st.toggle("ราคาสด (auto-refresh)", value=False)
    with st.expander("🧹 รายงานการ Clean ข้อมูล"):
        for s in dp.get_cleaning_report():
            st.write("•", s)
    st.caption("Provider: " + md.PROVIDER + ("  | API: ✅" if os.getenv("ANTHROPIC_API_KEY") else "  | API: ❌"))

# ---------- ส่วนบน: ชื่อกอง + ราคาสด ----------
m = rc.risk_summary(fund)
left, right = st.columns([3, 1])
with left:
    st.markdown(f"### {m['fund_name']}  `{fund}`")
    st.caption(f"ข้อมูล ณ {m['as_of']} · {m['observations']} วันทำการ")
with right:
    tick = md.get_tick(fund)
    st.metric("ราคาสด", f"{tick['price']:,.4f}", f"{tick['change_pct']:+.3f}%")

# ---------- การ์ดตัวชี้วัดความเสี่ยง ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Volatility (ต่อปี)", f"{m['annualized_volatility_pct']}%")
c2.metric("VaR 99% (รายวัน)", f"{m['VaR_99_daily_pct']}%")
c3.metric("Max Drawdown", f"{m['max_drawdown_pct']}%")
c4.metric("Sharpe Ratio", f"{m['sharpe_ratio']}")

dd_limit = 25 if fund != "ONE-BOND" else 8
status = ("warn", "เกินลิมิตนโยบาย") if m["max_drawdown_pct"] > dd_limit else ("ok", "อยู่ในกรอบนโยบาย")
st.markdown(f"<span class='badge {status[0]}'>Drawdown {m['max_drawdown_pct']}% · ลิมิต {dd_limit}% · {status[1]}</span>",
            unsafe_allow_html=True)

# ---------- กราฟ NAV + Drawdown ----------
series = dp.get_nav_series(fund)
nav = series["nav"]
g1, g2 = st.columns(2)
with g1:
    st.markdown("#### NAV")
    fig = go.Figure(go.Scatter(x=series["date"], y=nav, mode="lines", line=dict(color="#2e6df6", width=2)))
    fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10),
                      paper_bgcolor="white", plot_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)
with g2:
    st.markdown("#### Drawdown")
    dd = (nav / nav.cummax() - 1) * 100
    fig2 = go.Figure(go.Scatter(x=series["date"], y=dd, fill="tozeroy",
                                line=dict(color="#e24b4a", width=1.5)))
    fig2.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10),
                       paper_bgcolor="white", plot_bgcolor="white")
    st.plotly_chart(fig2, use_container_width=True)

# ---------- เปรียบเทียบทุกกอง ----------
st.markdown("#### เปรียบเทียบความเสี่ยงทุกกอง")
comp = pd.DataFrame([rc.risk_summary(f) for f in FUNDS])[
    ["fund_code", "annualized_volatility_pct", "VaR_99_daily_pct", "max_drawdown_pct", "sharpe_ratio", "return_ytd_pct"]
].rename(columns={"fund_code": "กอง", "annualized_volatility_pct": "Vol%", "VaR_99_daily_pct": "VaR99%",
                  "max_drawdown_pct": "MaxDD%", "sharpe_ratio": "Sharpe", "return_ytd_pct": "YTD%"})
st.dataframe(comp, use_container_width=True, hide_index=True)

# ---------- แชทกับ AI ----------
st.markdown("---")
st.markdown("### 💬 ถาม Risk Copilot")
st.caption("เช่น “ONE-EQ เกินลิมิต drawdown ไหม”, “เทียบทุกกอง Sharpe ดีสุด”, “นโยบาย AI governance ว่าไง”")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    if msg["role"] == "user" and isinstance(msg["content"], str):
        st.chat_message("user").markdown(msg["content"])
    elif msg["role"] == "assistant" and isinstance(msg["content"], list):
        txt = "".join(b["text"] for b in msg["content"] if b.get("type") == "text")
        if txt:
            st.chat_message("assistant").markdown(txt)


def run_agent(user_text: str):
    # guardrail: กรองนอกเรื่องก่อน เพื่อไม่เปลือง token ของลูปหลัก
    on_topic, _ = guardrail.is_on_topic(user_text)
    if not on_topic:
        st.session_state.messages.append({"role": "user", "content": user_text})
        st.chat_message("assistant").markdown(guardrail.REFUSAL_MSG)
        st.session_state.messages.append(
            {"role": "assistant", "content": [{"type": "text", "text": guardrail.REFUSAL_MSG}]})
        return

    client = llm_client.get_client()
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("assistant"):
        ph = st.empty()
        with st.spinner("กำลังวิเคราะห์..."):
            while True:
                resp = client.messages.create(
                    model=MODEL, max_tokens=1500, system=SYSTEM_PROMPT,
                    tools=t.ANTHROPIC_TOOLS, messages=st.session_state.messages)
                st.session_state.messages.append(
                    {"role": "assistant", "content": [b.model_dump() for b in resp.content]})
                if resp.stop_reason == "tool_use":
                    results = []
                    for b in resp.content:
                        if b.type == "tool_use":
                            with st.status(f"🔧 {b.name}", state="complete"):
                                st.write(b.input)
                            results.append({"type": "tool_result", "tool_use_id": b.id,
                                            "content": t.run_tool(b.name, b.input)})
                    st.session_state.messages.append({"role": "user", "content": results})
                    continue
                ph.markdown("".join(b.text for b in resp.content if b.type == "text"))
                break


prompt = st.chat_input("พิมพ์คำถามเรื่องความเสี่ยงกองทุน...")
if prompt:
    if not os.getenv("ANTHROPIC_API_KEY"):
        st.warning("กรุณาตั้งค่า ANTHROPIC_API_KEY ก่อนใช้แชท")
    else:
        st.chat_message("user").markdown(prompt)
        run_agent(prompt)

# auto-refresh สำหรับราคาสด
if live_on:
    import time
    time.sleep(3)
    st.rerun()
