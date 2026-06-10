"""
guardrail.py
------------
กรองคำถามก่อนส่งเข้าโมเดลหลัก (Sonnet + tools) เพื่อ "ประหยัด token"
ถ้าถามนอกเรื่อง (ไม่เกี่ยวกองทุน/ความเสี่ยง) -> ตอบสั้น ๆ ไม่ต้องรันลูป agentic ที่แพง

กลยุทธ์ 2 ชั้น:
  1) fast-path (ฟรี ไม่เรียก LLM): ถ้าเจอรหัสกอง/คำเฉพาะทาง -> อนุญาตทันที
  2) ถ้าไม่ชัด: เรียก Haiku (โมเดลถูก) ตัดสิน YES/NO ครั้งเดียว
     ถ้า NO -> ส่งข้อความ canned กลับ ไม่แตะ Sonnet เลย
"""
from __future__ import annotations
import os
import re

import data_pipeline as dp

# คำที่ชัดเจนว่าเกี่ยวกับงาน -> อนุญาตเลยไม่ต้องเรียก LLM
IN_SCOPE_TERMS = [
    "กองทุน", "กอง", "nav", "var", "drawdown", "วอล", "volatility", "ความเสี่ยง",
    "risk", "sharpe", "ผลตอบแทน", "return", "benchmark", "ลิมิต", "นโยบาย",
    "policy", "ราคา", "governance", "ดัชนี", "fund",
]

REFUSAL_MSG = (
    "ขอตอบเฉพาะเรื่องที่เกี่ยวกับกองทุนและการบริหารความเสี่ยงนะครับ "
    "เช่น ความเสี่ยง ผลตอบแทน VaR/Drawdown หรือเกณฑ์นโยบาย"
)

GATE_MODEL = "claude-haiku-4-5"  # โมเดลถูกไว้คัดกรอง


def _fast_allow(text: str) -> bool:
    low = text.lower()
    if any(term in low for term in IN_SCOPE_TERMS):
        return True
    # เจอรหัสกองในระบบ
    if any(code.lower() in low for code in dp.list_fund_codes()):
        return True
    return False


def is_on_topic(text: str) -> tuple[bool, str]:
    """
    คืน (อนุญาตไหม, เหตุผล/แหล่งที่ตัดสิน)
    ไม่มี API key หรือ fast-path ผ่าน -> ไม่เรียก LLM
    """
    if _fast_allow(text):
        return True, "fast-path"

    if not os.getenv("ANTHROPIC_API_KEY"):
        # ไม่มีคีย์: ปล่อยผ่าน (กันบล็อกผิดพลาดตอนเดโม)
        return True, "no-key-passthrough"

    try:
        import llm_client
        client = llm_client.get_client()
        r = client.messages.create(
            model=GATE_MODEL,
            max_tokens=5,
            system="ตอบ YES ถ้าคำถามเกี่ยวกับกองทุน/การลงทุน/การบริหารความเสี่ยง, ไม่งั้นตอบ NO. ตอบคำเดียว",
            messages=[{"role": "user", "content": text}],
        )
        verdict = "".join(b.text for b in r.content if b.type == "text").strip().upper()
        return verdict.startswith("YES"), f"gate:{GATE_MODEL}"
    except Exception:  # noqa
        return True, "gate-error-passthrough"


if __name__ == "__main__":
    tests = [
        "ONE-EQ เสี่ยงแค่ไหน",
        "drawdown เกินลิมิตไหม",
        "ช่วยเขียนกลอนรักให้หน่อย",
        "วันนี้อากาศเป็นยังไง",
        "VaR คืออะไร",
    ]
    for t in tests:
        ok, why = is_on_topic(t)
        print(f"{'✅ ตอบ' if ok else '⛔ ปฏิเสธ'}  [{why:22}]  {t}")
