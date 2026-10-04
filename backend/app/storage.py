from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings


class LocalStorage:
    def __init__(self, root: str | None = None):
        self.root = Path(root or get_settings().storage_path).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, content: bytes) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix not in {".csv", ".xlsx"}:
            raise ValueError("Only CSV and XLSX files are supported.")
        key = f"{uuid4().hex}{suffix}"
        target = (self.root / key).resolve()
        if target.parent != self.root:
            raise ValueError("Invalid storage path.")
        target.write_bytes(content)
        return key

    def path(self, key: str) -> Path:
        target = (self.root / key).resolve()
        if target.parent != self.root:
            raise ValueError("Invalid storage key.")
        return target

    def delete(self, key: str) -> None:
        target = self.path(key)
        if target.exists():
            target.unlink()
