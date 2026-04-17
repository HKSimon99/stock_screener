# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

WORKDIR /app

# ── 1. System build tools ───────────────────────────────────────────────────
# gcc/g++/make/autoconf required to compile TA-Lib C library from source.
# libpq-dev required for psycopg2-binary build.
# wget required to fetch TA-Lib source.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    autoconf \
    automake \
    libtool \
    libpq-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# ── 2. Build TA-Lib C library from source ──────────────────────────────────
# The Python TA-Lib package (>=0.6.8) wraps this C library (0.4.0 is the
# canonical stable release). Must be installed before `uv sync` pulls the
# Python bindings, otherwise the C headers won't be found.
ARG TALIB_VERSION=0.4.0
RUN wget -q \
        "http://prdownloads.sourceforge.net/ta-lib/ta-lib-${TALIB_VERSION}-src.tar.gz" \
    && tar -xzf "ta-lib-${TALIB_VERSION}-src.tar.gz" \
    && cd ta-lib \
    && ./configure --prefix=/usr \
    && make \
    && make install \
    && cd .. \
    && rm -rf ta-lib "ta-lib-${TALIB_VERSION}-src.tar.gz"

# ── 3. Install uv ──────────────────────────────────────────────────────────
RUN pip install --no-cache-dir uv

# ── 4. Install Python deps (separate layer so source changes don't re-pip) ─
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# ── 5. Copy application source ─────────────────────────────────────────────
COPY . .

# ── 6. Runtime ────────────────────────────────────────────────────────────
EXPOSE 8000
CMD uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
