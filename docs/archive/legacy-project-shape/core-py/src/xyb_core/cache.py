from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class CacheEntry:
    path: str
    size: int
    mtime_ns: int
    digest: str


def file_signature(path: str | Path) -> CacheEntry:
    file_path = Path(path)
    stat = file_path.stat()
    payload = f"{file_path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}".encode()
    return CacheEntry(
        path=str(file_path),
        size=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        digest=sha256(payload).hexdigest(),
    )
