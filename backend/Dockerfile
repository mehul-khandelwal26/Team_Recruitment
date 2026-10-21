FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source, migrations, and configs
COPY . .

EXPOSE 8000

# Run database migrations if PostgreSQL is configured, then start Uvicorn
CMD ["sh", "-c", "if [ \"$STORAGE_BACKEND\" = \"postgres\" ]; then alembic upgrade head; fi && uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT:-8000}"]
