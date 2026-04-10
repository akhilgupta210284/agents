# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools for any C-extension packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY agents/          agents/
COPY config/          config/
COPY etl/             etl/
COPY tools/           tools/
COPY utils/           utils/
COPY agentcore_app.py .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# AgentCore Runtime calls /invocations on this port
EXPOSE 8080

# Run as non-root for security (HIPAA best practice)
RUN adduser --disabled-password --gecos "" appuser
USER appuser

ENTRYPOINT ["python", "agentcore_app.py"]
