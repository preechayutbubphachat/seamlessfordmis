import hashlib
import json
from datetime import datetime
from pathlib import Path

from app.schemas.common import FileFingerprint


class FileHashService:
    @staticmethod
    def calculate_sha256(file_path: Path) -> str:
        digest = hashlib.sha256()
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def fingerprint(cls, file_path: Path) -> FileFingerprint:
        stat = file_path.stat()
        return FileFingerprint(
            filename=file_path.name,
            path=str(file_path.resolve()),
            sha256=cls.calculate_sha256(file_path),
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime),
        )

    @classmethod
    def manifest_hash(cls, fingerprints: list[FileFingerprint]) -> str:
        normalized = [
            {
                "filename": item.filename,
                "path": item.path,
                "sha256": item.sha256,
                "size_bytes": item.size_bytes,
                "modified_at": item.modified_at.isoformat(),
            }
            for item in sorted(fingerprints, key=lambda x: (x.filename, x.path))
        ]
        payload = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
