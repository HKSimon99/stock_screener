"""
Cloudflare R2 snapshot storage.

Uploads daily consensus snapshot JSON to an R2 bucket so clients can fetch
rankings directly from the CDN edge without hitting the API.

This module is a **no-op** when R2 credentials are absent from the
environment — set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY
(and optionally R2_BUCKET_NAME, R2_PUBLIC_URL) to enable.

Key naming convention (matches CDN URL pattern):
  snapshots/{market}/{asset_type}/{YYYY-MM-DD}.json
  snapshots/{market}/{asset_type}/latest.json   ← always points to today
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

_CONTENT_TYPE = "application/json"
_CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=60"


def _boto_client():
    """Lazy-import boto3 and return an S3 client pointed at R2."""
    import boto3  # type: ignore[import-untyped]  # noqa: PLC0415

    from app.core.config import settings  # noqa: PLC0415

    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def _snapshot_key(market: str, asset_type: str, snapshot_date: date) -> str:
    return f"snapshots/{market.lower()}/{asset_type}/{snapshot_date.isoformat()}.json"


def _latest_key(market: str, asset_type: str) -> str:
    return f"snapshots/{market.lower()}/{asset_type}/latest.json"


def _etag_for(body: bytes) -> str:
    """MD5 ETag matching S3/R2 convention (hex, no quotes)."""
    return hashlib.md5(body).hexdigest()  # noqa: S324 — ETag, not security-sensitive


def upload_snapshot(
    *,
    market: str,
    asset_type: str,
    snapshot_date: date,
    payload: dict[str, Any],
) -> str | None:
    """
    Serialise *payload* and upload it to R2 under the dated key.
    Also uploads a ``latest.json`` alias pointing to the same content.

    Returns the public CDN URL if R2_PUBLIC_URL is configured, else ``None``.
    No-op (returns ``None``) when R2 is not configured.
    """
    from app.core.config import settings  # noqa: PLC0415

    if not settings.r2_enabled:
        return None

    body = json.dumps(payload, separators=(",", ":"), default=str).encode()
    dated_key = _snapshot_key(market, asset_type, snapshot_date)
    latest_key = _latest_key(market, asset_type)
    etag = _etag_for(body)
    put_kwargs: dict[str, Any] = {
        "ContentType": _CONTENT_TYPE,
        "CacheControl": _CACHE_CONTROL,
        "Metadata": {
            "etag": etag,
            "market": market,
            "asset_type": asset_type,
            "snapshot_date": snapshot_date.isoformat(),
        },
    }

    try:
        client = _boto_client()
        client.put_object(
            Bucket=settings.r2_bucket_name,
            Key=dated_key,
            Body=body,
            **put_kwargs,
        )
        # Overwrite the "latest" alias so CDN clients always get the most recent
        client.put_object(
            Bucket=settings.r2_bucket_name,
            Key=latest_key,
            Body=body,
            **put_kwargs,
        )
        logger.info("R2 snapshot uploaded: %s (%d bytes, etag=%s)", dated_key, len(body), etag)
    except Exception:
        logger.exception("R2 snapshot upload failed for %s — continuing without CDN", dated_key)
        return None

    if settings.r2_public_url:
        return f"{settings.r2_public_url.rstrip('/')}/{dated_key}"
    return None


def snapshot_etag(
    market: str,
    asset_type: str,
    snapshot_date: date,
) -> str | None:
    """
    Fetch the ETag metadata for an uploaded snapshot without downloading the body.
    Returns ``None`` if R2 is not configured or the object doesn't exist.
    """
    from app.core.config import settings  # noqa: PLC0415

    if not settings.r2_enabled:
        return None

    key = _snapshot_key(market, asset_type, snapshot_date)
    try:
        client = _boto_client()
        head = client.head_object(Bucket=settings.r2_bucket_name, Key=key)
        # R2 stores the md5 ETag in the Metadata dict we set during upload,
        # and also in the standard ETag header (without quotes).
        meta_etag: str | None = head.get("Metadata", {}).get("etag")
        if meta_etag:
            return meta_etag
        raw_etag: str = head.get("ETag", "").strip('"')
        return raw_etag or None
    except Exception:
        return None
