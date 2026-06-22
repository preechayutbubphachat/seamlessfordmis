from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ParsedPdfPage:
    page_number: int
    text: str
    parse_status: str
    warning_message: str | None = None


class PdfTextImporter:
    @staticmethod
    def read_pages(path: Path) -> list[ParsedPdfPage]:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages: list[ParsedPdfPage] = []
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(ParsedPdfPage(page_number=index, text=text, parse_status="parsed"))
            else:
                pages.append(
                    ParsedPdfPage(
                        page_number=index,
                        text="",
                        parse_status="warning",
                        warning_message="ไม่พบข้อความที่ดึงได้จาก PDF หน้านี้",
                    )
                )
        return pages
