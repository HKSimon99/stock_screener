"""
OpenTelemetry setup for the Consensus API.

This module is a **no-op** when OTLP_ENDPOINT is not set in the environment,
so there is zero overhead in local development and CI.

Production setup (Grafana Cloud):
1. Set OTLP_ENDPOINT = https://otlp-gateway-prod-<region>.grafana.net/otlp
2. Set OTLP_HEADERS  = Authorization=Basic <base64(instanceId:apiToken)>
3. Set OTLP_SERVICE_NAME = consensus-api   (or override per deployment)
4. Optionally set OTLP_TRACES_SAMPLE_RATE (default 0.1 = 10%)

The FastAPI and SQLAlchemy instrumentations are applied lazily (called once
from main.py at app startup) and add no import-time cost.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


def setup_telemetry(app: "FastAPI", engine: "AsyncEngine | None" = None) -> None:
    """
    Configure OpenTelemetry tracing and instrument FastAPI + SQLAlchemy.

    Called once from ``app/main.py`` after the FastAPI application is created.
    Is a no-op when ``OTLP_ENDPOINT`` is absent from the environment.
    """
    from app.core.config import settings  # import here to avoid circular import

    if not settings.otlp_endpoint:
        return  # No-op: OTLP not configured

    try:
        _configure(app, engine, settings)
    except Exception:  # pragma: no cover
        logger.exception("Failed to initialise OpenTelemetry — tracing disabled")


def _configure(app: "FastAPI", engine: "AsyncEngine | None", settings) -> None:  # noqa: ANN001
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

    # ── Resource (service identity) ──────────────────────────────────────────
    resource = Resource(attributes={SERVICE_NAME: settings.otlp_service_name})

    # ── Sampler: send N % of traces to Grafana ───────────────────────────────
    sampler = TraceIdRatioBased(settings.otlp_traces_sample_rate)

    # ── Tracer provider ──────────────────────────────────────────────────────
    provider = TracerProvider(resource=resource, sampler=sampler)

    # ── OTLP exporter (HTTP/protobuf) ────────────────────────────────────────
    exporter = OTLPSpanExporter(
        endpoint=settings.otlp_endpoint.rstrip("/") + "/v1/traces",
        headers=settings.otlp_headers_dict,
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # ── FastAPI auto-instrumentation ─────────────────────────────────────────
    # Exclude health checks from traces to avoid noise.
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="/api/v1/health",
    )

    # ── HTTPx auto-instrumentation (outbound Clerk JWKS + data fetches) ──────
    HTTPXClientInstrumentor().instrument()

    # ── SQLAlchemy async engine instrumentation ───────────────────────────────
    if engine is not None:
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

            SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
        except Exception:  # pragma: no cover
            logger.warning("SQLAlchemy OTel instrumentation unavailable — skipped")

    logger.info(
        "OpenTelemetry tracing enabled → %s (sample_rate=%.0f%%)",
        settings.otlp_endpoint,
        settings.otlp_traces_sample_rate * 100,
    )
