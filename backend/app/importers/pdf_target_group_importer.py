from pathlib import Path

from app.importers.excel_target_group_importer import ParsedTargetGroupRow
from app.importers.pdf_scanned_importer import PdfScannedImporter
from app.importers.pdf_text_importer import PdfTextImporter


class PdfTargetGroupImporter:
    @staticmethod
    def read_rows(path: Path) -> list[ParsedTargetGroupRow]:
        text_pages = PdfTextImporter.read_pages(path)
        has_text = any(page.text for page in text_pages)
        if has_text:
            return [
                ParsedTargetGroupRow(
                    source_filename=path.name,
                    source_sheet_name="pdf",
                    source_sheet_index=0,
                    row_number=page.page_number,
                    values={
                        "pid": None,
                        "citizen_id": None,
                        "hn": None,
                        "full_name": None,
                        "birth_date": None,
                        "raw_pdf_text": page.text,
                        "parse_warning": page.warning_message,
                        "target_group_profile": "pdf_text_import_v1",
                    },
                )
                for page in text_pages
            ]

        # TODO: replace with OCR-backed extraction and review UI in scanned PDF phase.
        return [
            ParsedTargetGroupRow(
                source_filename=path.name,
                source_sheet_name="pdf_scan",
                source_sheet_index=0,
                row_number=page.page_number,
                values={
                    "pid": None,
                    "citizen_id": None,
                    "hn": None,
                    "full_name": None,
                    "birth_date": None,
                    "raw_pdf_text": None,
                    "parse_warning": page.warning_message,
                    "target_group_profile": "pdf_scanned_import_v1",
                },
            )
            for page in PdfScannedImporter.read_pages(path)
        ]
