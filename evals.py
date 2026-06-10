"""
evals.py
--------
ชุดประเมินคุณภาพระบบ (วัดได้โดยไม่ต้องเดา) แบ่งเป็น 4 ด้าน:

1) RAG retrieval   : ถามแล้วดึง "หมวดนโยบายที่ถูก" ติด top-k ไหม -> Hit-rate@k, MRR
2) Numeric metrics : ตัวเลขความเสี่ยงสมเหตุสมผลไหม (bond วอลต่ำกว่า equity, VaR99>VaR95, ...)
3) Guardrail       : กรองในเรื่อง/นอกเรื่องถูกไหม -> Accuracy
4) Tool selection  : (ต้องมี ANTHROPIC_API_KEY) ถามแล้ว agent เรียก tool ถูกตัวไหม

รัน: python evals.py
"""
from __future__ import annotations
import os

import rag
import risk_core as rc
import guardrail


def eval_rag():
    cases = [
        ("ลิมิต VaR ของกองหุ้นเท่าไร", "VaR"),
        ("drawdown เกินเท่าไรต้องรายงาน", "Drawdown"),
        ("ใช้ AI ในองค์กรได้แค่ไหน", "AI Governance"),
        ("ขั้นตอนเมื่อเกินลิมิตทำอย่างไร", "Escalation"),
        ("volatility กองตราสารหนี้ไม่ควรเกินเท่าไร", "ลิมิตความเสี่ยง"),
    ]
    r = rag.get_rag()
    hits, rr = 0, 0.0
    for q, expect in cases:
        results = r.search(q, top_k=3)
        rank = next((i for i, h in enumerate(results) if expect.lower() in h["section"].lower()), None)
        if rank is not None:
            hits += 1
            rr += 1 / (rank + 1)
    n = len(cases)
    return {"hit_rate@3": round(hits / n, 2), "MRR": round(rr / n, 2), "n": n}


def eval_numeric():
    checks = []
    eq = rc.risk_summary("ONE-EQ")
    bond = rc.risk_summary("ONE-BOND")
    checks.append(("bond วอลต่ำกว่า equity", bond["annualized_volatility_pct"] < eq["annualized_volatility_pct"]))
    checks.append(("VaR99 >= VaR95 (equity)", eq["VaR_99_daily_pct"] >= eq["VaR_95_daily_pct"]))
    checks.append(("max drawdown ไม่ติดลบ", eq["max_drawdown_pct"] >= 0))
    checks.append(("วอล bond > 0", bond["annualized_volatility_pct"] > 0))
    passed = sum(1 for _, ok in checks if ok)
    return {"passed": passed, "total": len(checks),
            "details": [(name, "PASS" if ok else "FAIL") for name, ok in checks]}


def eval_guardrail():
    cases = [
        ("ONE-EQ เสี่ยงแค่ไหน", True),
        ("VaR คืออะไร", True),
        ("drawdown เกินลิมิตไหม", True),
        ("ช่วยเขียนกลอนรักหน่อย", False),
        ("วิธีทำต้มยำกุ้ง", False),
    ]
    # ประเมินเฉพาะ fast-path (ฟรี) — วัดว่า "ในเรื่อง" ถูกจับโดยไม่ต้องเรียก LLM
    correct = 0
    for text, expected_in in cases:
        fast = guardrail._fast_allow(text)
        # in-scope ควร fast-allow=True; out-scope ควร fast-allow=False (แล้วค่อยให้ gate ตัด)
        if fast == expected_in:
            correct += 1
    return {"fast_path_accuracy": round(correct / len(cases), 2), "n": len(cases)}


def eval_tool_selection():
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {"skipped": "ตั้ง ANTHROPIC_API_KEY เพื่อรัน eval นี้"}
    import anthropic
    import agent_tools as t
    cases = [
        ("ONE-EQ วอลเท่าไร", "get_risk_metrics"),
        ("ราคา ONE-EQ ตอนนี้", "get_live_price"),
        ("ลิมิต drawdown ตามนโยบาย", "search_risk_policy"),
        ("เทียบความเสี่ยงทุกกอง", "compare_funds"),
    ]
    client = anthropic.Anthropic()
    correct = 0
    for q, expected_tool in cases:
        r = client.messages.create(model="claude-sonnet-4-6", max_tokens=300,
                                   tools=t.ANTHROPIC_TOOLS,
                                   messages=[{"role": "user", "content": q}])
        called = [b.name for b in r.content if b.type == "tool_use"]
        if expected_tool in called:
            correct += 1
    return {"tool_accuracy": round(correct / len(cases), 2), "n": len(cases)}


if __name__ == "__main__":
    print("1) RAG retrieval :", eval_rag())
    print("2) Numeric       :", eval_numeric())
    print("3) Guardrail     :", eval_guardrail())
    print("4) Tool selection:", eval_tool_selection())
