"""Tests for atomic env store behavior and validation rollback."""

from pathlib import Path

import pytest

from src.tui.services.env_store import EnvStore


def test_env_store_save_is_atomic_and_creates_backup(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text("LOG_LEVEL=INFO\n", encoding="utf-8")

    store = EnvStore(str(env_path))
    store.save(
        {
            "LOG_LEVEL": "DEBUG",
            "DEFAULT_TEMPERATURE": "0.7",
        },
        managed_keys=["LOG_LEVEL", "DEFAULT_TEMPERATURE"],
    )

    assert env_path.read_text(encoding="utf-8") == "LOG_LEVEL=DEBUG\nDEFAULT_TEMPERATURE=0.7\n"
    backup_path = env_path.with_suffix(env_path.suffix + ".bak")
    assert backup_path.exists()
    assert backup_path.read_text(encoding="utf-8") == "LOG_LEVEL=INFO\n"
    assert not env_path.with_suffix(env_path.suffix + ".tmp").exists()


def test_env_store_validation_failure_keeps_existing_file(tmp_path: Path):
    env_path = tmp_path / ".env"
    original = "DEFAULT_TEMPERATURE=0.7\nLOG_LEVEL=INFO\n"
    env_path.write_text(original, encoding="utf-8")

    store = EnvStore(str(env_path))

    with pytest.raises(ValueError):
        store.save(
            {
                "DEFAULT_TEMPERATURE": "9.9",
                "LOG_LEVEL": "INFO",
            },
            managed_keys=["DEFAULT_TEMPERATURE", "LOG_LEVEL"],
        )

    assert env_path.read_text(encoding="utf-8") == original
