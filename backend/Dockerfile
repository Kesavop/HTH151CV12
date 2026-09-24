# Hugging Face Spaces (Docker) or any server: builds the Gladiators AI backend
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data/uploads && chmod -R 777 /app/data

ENV HF_HOME=/tmp/hf YOLO_CONFIG_DIR=/tmp/yolo
EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
