# --- Build stage: install dependencies into a layer that caches well ---
FROM python:3.12-slim AS base

WORKDIR /app

# Install deps first (layer caches unless pyproject.toml changes)
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/

# Non-root user for production security
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
