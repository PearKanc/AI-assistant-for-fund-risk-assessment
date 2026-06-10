FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# ติดตั้ง dependencies ก่อน (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอกโค้ดทั้งหมด
COPY . .

# สร้างข้อมูลดิบตอน build (ในงานจริงจะดึงจาก DB/Bloomberg แทน)
RUN python make_raw_data.py

EXPOSE 8501
# RAG จะต่อ Qdrant ผ่าน QDRANT_URL (ตั้งใน compose)
CMD ["streamlit", "run", "chatbot_app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
