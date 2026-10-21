FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# build-essential is only needed while native wheels are compiled. Keeping it in
# a separate stage means the runtime image carries no compiler toolchain.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt


FROM python:3.11-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

COPY . .

# Run unprivileged: this app ingests private conversation logs, so a compromised
# process should not also be root inside the container.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data/uploads \
    && chown -R appuser:appuser /app/data
USER appuser

EXPOSE 8000

# /api/health does not touch the database, so this reports process liveness
# rather than database readiness.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
