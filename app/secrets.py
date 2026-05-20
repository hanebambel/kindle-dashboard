import json
from pathlib import Path


class MissingSecret(Exception):
    pass


class SecretsStore:
    """Resolves config values. A value starting with '$' is looked up in
    secrets.json; any other string passes through unchanged."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def resolve(self, value: str) -> str:
        if not isinstance(value, str) or not value.startswith("$"):
            return value
        key = value[1:]
        secrets = self._load()
        if key not in secrets:
            raise MissingSecret(key)
        return secrets[key]
