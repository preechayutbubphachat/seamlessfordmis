import json
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from app.schemas.common import FileFingerprint, SourceFileResponse
from app.utils.files import detect_file_type


@dataclass(slots=True)
class FileHashService:
    @staticmethod
    def fingerprint(path: Path) -> FileFingerprint:
        digest = sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        stat = path.stat()
        return FileFingerprint(
            filename=path.name,
            path=str(path.resolve()),
            sha256=digest.hexdigest(),
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
            for item in sorted(fingerprints, key=lambda item: (item.filename, item.path))
        ]
        payload = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return sha256(payload).hexdigest()

    @classmethod
    def as_source_file_response(cls, fingerprint: FileFingerprint) -> SourceFileResponse:
        return SourceFileResponse(
            file_name=fingerprint.filename,
            file_path=fingerprint.path,
            file_type=detect_file_type(fingerprint.filename),
            sha256=fingerprint.sha256,
            size_bytes=fingerprint.size_bytes,
            modified_at=fingerprint.modified_at,
        )
