from pathlib import Path

from app.services.file_hash_service import FileHashService
from app.utils.files import is_supported_source_file


def test_fingerprint_uses_sha256(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_text("hospital-data", encoding="utf-8")

    fingerprint = FileHashService.fingerprint(file_path)

    assert fingerprint.filename == "sample.txt"
    assert len(fingerprint.sha256) == 64
    assert fingerprint.size_bytes == len("hospital-data".encode("utf-8"))


def test_supported_source_file_ignores_excel_lock_file(tmp_path: Path) -> None:
    file_path = tmp_path / "~$locked.xlsx"
    file_path.write_text("placeholder", encoding="utf-8")

    assert is_supported_source_file(file_path) is False
