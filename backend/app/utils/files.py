from pathlib import Path


SUPPORTED_EXCEL_SUFFIXES = {".xlsx", ".xls", ".csv"}
SUPPORTED_PDF_SUFFIXES = {".pdf"}
SUPPORTED_SOURCE_SUFFIXES = SUPPORTED_EXCEL_SUFFIXES | SUPPORTED_PDF_SUFFIXES


def detect_file_type(filename: str | Path) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix in {".xlsx", ".xls"}:
        return "excel"
    if suffix in SUPPORTED_PDF_SUFFIXES:
        return "pdf"
    raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")


def is_supported_source_file(path: Path) -> bool:
    return (
        path.is_file()
        and not path.name.startswith("~$")
        and path.suffix.lower() in SUPPORTED_SOURCE_SUFFIXES
    )
