import json
from pathlib import Path

import pytest

from app.secrets import SecretsStore, MissingSecret


def test_resolve_plain_value_unchanged(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.json"
    secrets_file.write_text("{}")
    store = SecretsStore(secrets_file)
    assert store.resolve("hello") == "hello"


def test_resolve_dollar_reference(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.json"
    secrets_file.write_text(json.dumps({"grafana_token": "abc123"}))
    store = SecretsStore(secrets_file)
    assert store.resolve("$grafana_token") == "abc123"


def test_resolve_missing_raises(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.json"
    secrets_file.write_text("{}")
    store = SecretsStore(secrets_file)
    with pytest.raises(MissingSecret):
        store.resolve("$nope")


def test_resolve_missing_file_no_secrets(tmp_path: Path) -> None:
    store = SecretsStore(tmp_path / "absent.json")
    assert store.resolve("plain") == "plain"
    with pytest.raises(MissingSecret):
        store.resolve("$anything")
