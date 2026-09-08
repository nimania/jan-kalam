FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# System deps for psycopg (Postgres driver)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# Default command; docker-compose overrides per service (web / worker).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
