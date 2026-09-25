FROM python:3.13.15-slim-bookworm

ENV PYTHONPATH=/app/backend
WORKDIR /app/backend
RUN pip install --no-cache-dir \
    fastapi==0.141.1 sqlalchemy==2.0.54 'psycopg[binary]==3.3.3' \
    alembic==1.17.2 boto3==1.42.73 uvicorn==0.41.0 pillow==12.1.1
COPY backend/ ./
RUN pip install --no-cache-dir --no-deps .
COPY evaluation/ /app/evaluation/
COPY infra/deploy/init.py /app/init.py
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
