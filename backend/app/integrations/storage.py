from pathlib import Path
from typing import Protocol
import shutil
from app.core.config import settings


class ObjectStorage(Protocol):
    def write(self, key: str, contents: bytes) -> None: ...
    def path(self, key: str) -> Path: ...
    def delete(self, key: str) -> None: ...
    def copy(self, source: str, destination: str) -> None: ...


class LocalStorage:
    def __init__(self):
        self.root = Path(settings().storage_path).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key):
        if not key or any(c not in "0123456789abcdef-" for c in key):
            raise ValueError("Invalid storage key")
        return self.root / key

    def write(self, key, contents):
        with self.path(key).open("xb") as handle:
            handle.write(contents)

    def delete(self, key):
        self.path(key).unlink(missing_ok=True)

    def copy(self, source, destination):
        shutil.copyfile(self.path(source), self.path(destination))


storage = LocalStorage()
