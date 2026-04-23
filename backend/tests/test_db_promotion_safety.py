import pytest

from db_promotion_repair import reset_target_schema
from promote_local_to_neon import reset_confirmation_text, validate_target_reset_confirmation


REMOTE_TARGET_URL = "postgresql://user:pass@ep-example.us-east-1.aws.neon.tech/neondb"
LOCAL_TARGET_URL = "postgresql://user:pass@localhost:5432/consensus_target"


def test_reset_target_schema_refuses_production_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(RuntimeError, match="APP_ENV=production"):
        reset_target_schema(LOCAL_TARGET_URL, schema="consensus_app")


def test_remote_target_reset_requires_explicit_flag(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")

    with pytest.raises(SystemExit) as exc:
        validate_target_reset_confirmation(
            REMOTE_TARGET_URL,
            schema="consensus_app",
            allow_remote_target_reset=False,
            confirm_target_reset="",
        )

    assert "Refusing destructive schema reset on a non-local target" in str(exc.value)
    assert reset_confirmation_text(REMOTE_TARGET_URL, "consensus_app") in str(exc.value)


def test_remote_target_reset_requires_exact_confirmation(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")

    with pytest.raises(SystemExit) as exc:
        validate_target_reset_confirmation(
            REMOTE_TARGET_URL,
            schema="consensus_app",
            allow_remote_target_reset=True,
            confirm_target_reset="RESET consensus_app",
        )

    assert "confirmation text did not match" in str(exc.value)


def test_remote_target_reset_accepts_explicit_matching_confirmation(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")

    validate_target_reset_confirmation(
        REMOTE_TARGET_URL,
        schema="consensus_app",
        allow_remote_target_reset=True,
        confirm_target_reset=reset_confirmation_text(REMOTE_TARGET_URL, "consensus_app"),
    )


def test_remote_target_reset_refuses_production_environment_even_with_confirmation(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(SystemExit) as exc:
        validate_target_reset_confirmation(
            REMOTE_TARGET_URL,
            schema="consensus_app",
            allow_remote_target_reset=True,
            confirm_target_reset=reset_confirmation_text(REMOTE_TARGET_URL, "consensus_app"),
        )

    assert "APP_ENV=production" in str(exc.value)


def test_local_target_reset_does_not_need_remote_confirmation(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")

    validate_target_reset_confirmation(
        LOCAL_TARGET_URL,
        schema="consensus_app",
        allow_remote_target_reset=False,
        confirm_target_reset="",
    )
