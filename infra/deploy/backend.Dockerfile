FROM python:3.13.15-slim-bookworm

ENV PYTHONPATH=/app/backend YOLO_CONFIG_DIR=/tmp/ultralytics
WORKDIR /app/backend
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.10.12
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project --format requirements-txt > /tmp/requirements.txt \
    && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.10.0 torchvision==0.25.0 \
    && pip install --no-cache-dir -r /tmp/requirements.txt
COPY backend/ ./
COPY artifacts/dataset/Свод*.xlsx /app/artifacts/dataset/
RUN pip install --no-cache-dir --no-deps .
COPY evaluation/ /app/evaluation/
COPY infra/deploy/init.py /app/init.py
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
