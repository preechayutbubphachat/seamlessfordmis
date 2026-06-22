from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ParsedScannedPdfPage:
    page_number: int
    parse_status: str
    warning_message: str


class PdfScannedImporter:
    @staticmethod
    def read_pages(path: Path) -> list[ParsedScannedPdfPage]:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return [
            ParsedScannedPdfPage(
                page_number=index,
                parse_status="needs_review",
                warning_message="TODO: scanned PDF OCR review is still required before extracting structured fields.",
            )
            for index, _ in enumerate(reader.pages, start=1)
        ]
