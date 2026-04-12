FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend:/app

WORKDIR /app/backend

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend /app/backend
COPY worker /app/worker

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
