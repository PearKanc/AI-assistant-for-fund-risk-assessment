# Deploy ขึ้น Azure

ระบบมี 2 ส่วนที่ต้องรันบนคลาวด์: **app (Streamlit)** + **Qdrant** และต้องเข้าถึง **Claude**
แนะนำใช้ **Azure Container Apps (ACA)** เพราะรัน container ได้ตรง ๆ scale ได้ จัดการ secret/ingress ให้

## ส่วนที่ 1 — จะเรียก Claude ยังไงบน Azure (เลือก 1 ใน 2)

ทางเลือก A — Anthropic API ตรง (ง่ายสุด)
- เก็บ `ANTHROPIC_API_KEY` ไว้ใน Azure Key Vault แล้วฉีดเป็น secret ของ Container App
- โค้ดใช้ `LLM_PLATFORM=anthropic` (ดีฟอลต์)

ทางเลือก B — Claude ผ่าน Microsoft Foundry (เหมาะองค์กร/บลจ.)
- Claude (Sonnet 4.6, Haiku 4.5, Opus 4.8 ฯลฯ) ใช้ได้ใน Foundry แล้ว คิดเงินผ่าน Azure Marketplace
  ใช้ Azure agreement/MACC เดิมได้ ไม่ต้องอนุมัติ vendor แยก
- ภูมิภาคที่มี Claude ตอนนี้: East US 2 และ Sweden Central (Global Standard deployment)
- ขั้นตอน: สร้าง Foundry resource -> deploy โมเดล (เช่น `claude-sonnet-4-6`) -> เอา key/endpoint
- โค้ดสลับด้วย env (ไม่ต้องแก้โปรแกรม):
  ```
  LLM_PLATFORM=foundry
  ANTHROPIC_FOUNDRY_API_KEY=<key จาก Foundry>
  ANTHROPIC_FOUNDRY_RESOURCE=<ชื่อ resource>
  ```
  (`llm_client.py` จะเลือก `AnthropicFoundry` ให้เอง; `MODEL` = ชื่อ deployment)
- ใช้ Entra ID auth แทน key ได้เพื่อความปลอดภัยระดับองค์กร (จัดสิทธิ์ผ่าน Azure RBAC)
- หมายเหตุ: ช่วง preview การประมวลผลยังรันบน infra ของ Anthropic — ถ้าต้องการ data residency
  EU เต็มรูปแบบ Foundry ระบุว่า "กำลังมาในปี 2026" ให้เช็กหน้านโยบาย compliance ก่อนใช้ข้อมูลจริง

## ส่วนที่ 2 — คำสั่ง deploy (Azure Container Apps)

```bash
# 0) ล็อกอิน + ตัวแปร
az login
RG=rg-risk-copilot ; LOC=southeastasia ; ACR=acrriskcopilot$RANDOM

# 1) resource group + container registry แล้ว build image ขึ้น ACR (build บนคลาวด์ ไม่ต้องมี docker เครื่องตัวเอง)
az group create -n $RG -l $LOC
az acr create -n $ACR -g $RG --sku Basic --admin-enabled true
az acr build -r $ACR -t risk-copilot:latest .

# 2) Container Apps environment
az containerapp env create -n env-risk -g $RG -l $LOC

# 3) Qdrant (internal ingress) + ดิสก์ถาวรด้วย Azure Files (เก็บ vector ไม่หายเมื่อ restart)
az containerapp create -n qdrant -g $RG --environment env-risk \
  --image qdrant/qdrant:latest --target-port 6333 --ingress internal --min-replicas 1
#   (ผูก Azure Files volume ที่ /qdrant/storage ตามเอกสาร ACA storage mounts)

# 4) เก็บคีย์เป็น secret แล้ว deploy app (external ingress ที่พอร์ต 8501)
az containerapp create -n risk-app -g $RG --environment env-risk \
  --image $ACR.azurecr.io/risk-copilot:latest \
  --target-port 8501 --ingress external --min-replicas 1 \
  --secrets anthropic-key=$ANTHROPIC_API_KEY \
  --env-vars QDRANT_URL=http://qdrant:6333 MARKET_PROVIDER=simulated \
             LLM_PLATFORM=anthropic ANTHROPIC_API_KEY=secretref:anthropic-key

# 5) เอา URL มาเปิด
az containerapp show -n risk-app -g $RG --query properties.configuration.ingress.fqdn -o tsv
```

## ส่วนที่ 3 — production checklist
- เก็บ secret ทั้งหมดใน **Azure Key Vault** (ไม่ฮาร์ดโค้ด/ไม่ commit)
- ใส่ auth หน้า Streamlit (เช่น Azure AD / Easy Auth ของ ACA) ก่อนเปิดให้ภายในใช้
- ติด **Azure Monitor / Log Analytics** ดู latency, error, token usage
- Qdrant ใช้ดิสก์ถาวร (Azure Files) + เปิด snapshot สำรอง
- เปลี่ยน `MARKET_PROVIDER` เป็นตัวต่อข้อมูลจริง และต่อ `data_pipeline.load_raw()` เข้าฐาน NAV จริง
