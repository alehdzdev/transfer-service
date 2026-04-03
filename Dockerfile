FROM python:3.12-slim

WORKDIR /app

# 1. Install dependencies only (this layer caches until pyproject.toml changes).
#    Create a minimal placeholder so `pip install .` can resolve deps.
COPY pyproject.toml .
RUN mkdir app && touch app/__init__.py \
    && pip install --no-cache-dir . \
    && rm -rf app

# 2. Copy real application code and install the package properly.
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/
RUN pip install --no-cache-dir .

# Non-root user for production security
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
