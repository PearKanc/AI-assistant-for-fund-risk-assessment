AI Dashboard + Copilot สำหรับบริหารความเสี่ยงกองทุน 

1. เปิด terminal
2. package ที่ต้องติดตั้งก่อนการใช้งาน
pip3 install streamlit anthropic pandas numpy scikit-learn qdrant-client plotly fastmcp

3. export API Key
- Windows (PowerShell)
$env:ANTHROPIC_API_KEY="sk-ant-xxxxx"
- Mac / Linux
export ANTHROPIC_API_KEY=sk-ant-xxxxx

4.สร้างข้อมูล
พิมพ์คำสั่ง python make_raw_data.py ที่ terminal จะได้ไฟล์ raw_nav.csv (ข้อมูลดิบจำลอง) ใน folder data

5.เปิด dashboard
streamlit run chatbot_app.py 

หมายเหตุ:
-ตรวจสอบการทำ RAG ได้โดยพิมพ์ python rag.py  ที่ terminal
-ดูคะแนนประเมิน ได้ที่ python evals.py 