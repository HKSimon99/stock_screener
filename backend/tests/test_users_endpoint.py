"""
Tests for /api/v1/users/me and /api/v1/users/me/accept-tos.

Covers:
  - GET /me auto-creates the user row on first call
  - tos_accepted is False until POST /me/accept-tos succeeds
  - POST /me/accept-tos with the wrong version returns 409
  - POST /me/accept-tos with the right version sets tos_accepted_at + email
  - Bumping CURRENT_TOS_VERSION invalidates a previously-accepted user
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.api.v1.endpoints import users as users_endpoint
from app.models.user import User


@pytest.mark.asyncio
async def test_get_me_creates_user_row_and_reports_unaccepted(client, db_session):
    response = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer test"})
    assert response.status_code == 200
    body = response.json()

    assert body["clerk_user_id"] == "user_test_123"
    assert body["tos_accepted"] is False
    assert body["tos_accepted_at"] is None
    assert body["tos_version"] is None
    assert body["current_tos_version"] == users_endpoint.CURRENT_TOS_VERSION

    # User row was created lazily.
    rows = (await db_session.execute(select(User).where(User.clerk_user_id == "user_test_123"))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_accept_tos_with_wrong_version_returns_409(client):
    response = await client.post(
        "/api/v1/users/me/accept-tos",
        json={"version": "2020-01-01"},
        headers={"Authorization": "Bearer test"},
    )
    assert response.status_code == 409
    assert "version mismatch" in response.json()["detail"]


@pytest.mark.asyncio
async def test_accept_tos_with_correct_version_records_acceptance(client, db_session):
    response = await client.post(
        "/api/v1/users/me/accept-tos",
        json={"version": users_endpoint.CURRENT_TOS_VERSION, "email": "kyu@example.com"},
        headers={"Authorization": "Bearer test"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["tos_accepted"] is True
    assert body["tos_accepted_at"] is not None
    assert body["tos_version"] == users_endpoint.CURRENT_TOS_VERSION
    assert body["email"] == "kyu@example.com"

    user = (await db_session.execute(select(User).where(User.clerk_user_id == "user_test_123"))).scalars().first()
    assert user is not None
    assert user.tos_accepted_at is not None
    assert user.email == "kyu@example.com"


@pytest.mark.asyncio
async def test_bumping_current_tos_version_invalidates_prior_acceptance(client, db_session, monkeypatch):
    # First, accept the current version.
    accept = await client.post(
        "/api/v1/users/me/accept-tos",
        json={"version": users_endpoint.CURRENT_TOS_VERSION},
        headers={"Authorization": "Bearer test"},
    )
    assert accept.status_code == 200
    assert accept.json()["tos_accepted"] is True

    # Simulate a ToS bump on the server.
    monkeypatch.setattr(users_endpoint, "CURRENT_TOS_VERSION", "9999-01-01")

    # GET /me must now report tos_accepted=False, prompting the modal again.
    me = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer test"})
    body = me.json()
    assert body["tos_accepted"] is False
    assert body["current_tos_version"] == "9999-01-01"
    # tos_accepted_at remains populated (we keep the audit trail) but the version mismatch invalidates it.
    assert body["tos_accepted_at"] is not None
    assert body["tos_version"] != "9999-01-01"
