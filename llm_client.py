"""
llm_client.py
-------------
เลือกช่องทางเรียก Claude ด้วย env เดียว เพื่อให้ย้ายขึ้น Azure ได้โดยไม่แก้โค้ดหลัก

LLM_PLATFORM=anthropic (ดีฟอลต์) -> เรียก Anthropic API ตรง (ใช้ ANTHROPIC_API_KEY)
LLM_PLATFORM=foundry             -> เรียกผ่าน Microsoft Foundry บน Azure
    SDK จะอ่าน env: ANTHROPIC_FOUNDRY_API_KEY + ANTHROPIC_FOUNDRY_RESOURCE
    (หรือ ANTHROPIC_FOUNDRY_BASE_URL) เอง
    บน Foundry ค่าพารามิเตอร์ model = ชื่อ deployment (ดีฟอลต์ตรงกับ model id เช่น claude-sonnet-4-6)
"""
from __future__ import annotations
import os


def get_client():
    platform = os.getenv("LLM_PLATFORM", "anthropic").lower()
    if platform == "foundry":
        from anthropic import AnthropicFoundry
        return AnthropicFoundry()
    from anthropic import Anthropic
    return Anthropic()


if __name__ == "__main__":
    for p in ("anthropic", "foundry"):
        os.environ["LLM_PLATFORM"] = p
        from anthropic import Anthropic, AnthropicFoundry
        cls = AnthropicFoundry if p == "foundry" else Anthropic
        print(f"LLM_PLATFORM={p:10} -> จะใช้ {cls.__name__}")
