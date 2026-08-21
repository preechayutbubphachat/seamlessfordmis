<?php

namespace Tests\Feature;

use App\Services\Import\ImportPreviewService;
use App\Services\Import\XlsxSourceParser;
use PhpOffice\PhpSpreadsheet\Cell\DataType;
use PhpOffice\PhpSpreadsheet\Spreadsheet;
use PhpOffice\PhpSpreadsheet\Style\NumberFormat;
use PhpOffice\PhpSpreadsheet\Writer\Xlsx;
use Tests\TestCase;

final class XlsxSourceImportTest extends TestCase
{
    public function test_one_visible_worksheet_is_parsed_through_the_csv_preview_contract(): void
    {
        $path = $this->workbook(function (Spreadsheet $book): void {
            $sheet = $book->getActiveSheet();
            $sheet->setTitle('Source');
            $sheet->fromArray([['CID', 'service_key'], [null, 'SYN_ALPHA']]);
            $sheet->setCellValueExplicit('A2', '0123456789016', DataType::TYPE_STRING);
        });

        try {
            $preview = (new XlsxSourceParser)->parseFile($path, ['cid', 'service_key']);

            $this->assertSame(1, $preview['total_rows']);
            $this->assertSame(1, $preview['valid_rows']);
            $this->assertSame('0123456789016', $preview['rows'][0]['raw_cid']);
            $this->assertSame('0123456789016', $preview['rows'][0]['normalized_cid']);
            $this->assertSame([], $preview['errors']);
        } finally {
            @unlink($path);
        }
    }

    public function test_unexpected_xlsx_reader_failure_uses_bounded_error_contract(): void
    {
        $path = $this->workbook(function (Spreadsheet $book): void {
            $book->getActiveSheet()->fromArray([
                ['cid', 'service_key'],
                ['1234567890121', 'SYN_ALPHA'],
            ]);
        });

        try {
            $preview = (new XlsxSourceParser(
                readerFactory: static fn (): object => new class
                {
                    public function setReadDataOnly(bool $value): void {}

                    public function setReadEmptyCells(bool $value): void {}

                    public function setIncludeCharts(bool $value): void {}

                    public function setAllowExternalImages(bool $value): void {}

                    public function load(string $path): object
                    {
                        throw new \RuntimeException('SENSITIVE_INTERNAL_CANARY C:\\internal\\secret\\patient-data.txt');
                    }
                },
            ))->parseFile($path, ['cid', 'service_key']);

            $this->assertSame('XLSX_PARSE_FAILED', $preview['errors'][0]['code']);
            $this->assertSame('Unable to read XLSX file.', $preview['errors'][0]['message']);
            $this->assertStringNotContainsString('SENSITIVE_INTERNAL_CANARY', json_encode($preview, JSON_THROW_ON_ERROR));
            $this->assertStringNotContainsString('C:\\internal\\secret\\patient-data.txt', json_encode($preview, JSON_THROW_ON_ERROR));
        } finally {
            @unlink($path);
        }
    }

    public function test_import_preview_service_dispatches_xlsx_without_changing_csv_semantics(): void
    {
        $path = $this->workbook(function (Spreadsheet $book): void {
            $sheet = $book->getActiveSheet();
            $sheet->fromArray([
                ['cid', 'service_key'],
                [null, 'SYN_ALPHA'],
            ]);
            $sheet->setCellValueExplicit('A2', '1234567890121', DataType::TYPE_STRING);
        });

        try {
            $preview = (new ImportPreviewService)->previewSourceFile($path, ['cid', 'service_key'], 'xlsx');

            $this->assertSame(1, $preview['total_rows']);
            $this->assertSame('valid', $preview['rows'][0]['identifier_status']);
        } finally {
            @unlink($path);
        }
    }

    public function test_multiple_or_hidden_worksheets_fail_closed(): void
    {
        $multiple = $this->workbook(function (Spreadsheet $book): void {
            $book->createSheet()->setTitle('Second');
        });
        $hidden = $this->workbook(function (Spreadsheet $book): void {
            $book->getActiveSheet()->setSheetState('hidden');
        });

        try {
            $multiplePreview = (new XlsxSourceParser)->parseFile($multiple);
            $hiddenPreview = (new XlsxSourceParser)->parseFile($hidden);

            $this->assertSame('xlsx_single_sheet_required', $multiplePreview['errors'][0]['code']);
            $this->assertSame('xlsx_visible_sheet_required', $hiddenPreview['errors'][0]['code']);
        } finally {
            @unlink($multiple);
            @unlink($hidden);
        }
    }

    public function test_numeric_and_formula_cid_cells_are_rejected_without_reconstruction(): void
    {
        $numeric = $this->workbook(function (Spreadsheet $book): void {
            $sheet = $book->getActiveSheet();
            $sheet->fromArray([['cid'], [1234567890121]]);
        });
        $formula = $this->workbook(function (Spreadsheet $book): void {
            $sheet = $book->getActiveSheet();
            $sheet->fromArray([['cid'], ['1234567890121']]);
            $sheet->setCellValue('A2', '=1+1');
        });

        try {
            $numericPreview = (new XlsxSourceParser)->parseFile($numeric);
            $formulaPreview = (new XlsxSourceParser)->parseFile($formula);

            $this->assertSame('xlsx_cid_must_be_text', $numericPreview['errors'][0]['code']);
            $this->assertSame('xlsx_formula_rejected', $formulaPreview['errors'][0]['code']);
        } finally {
            @unlink($numeric);
            @unlink($formula);
        }
    }

    public function test_missing_and_duplicate_headers_reuse_csv_error_codes(): void
    {
        $missing = $this->workbook(function (Spreadsheet $book): void {
            $book->getActiveSheet()->fromArray([['service_key'], ['SYN_ALPHA']]);
        });
        $duplicate = $this->workbook(function (Spreadsheet $book): void {
            $book->getActiveSheet()->fromArray([['cid', 'CID'], ['1234567890121', '1234567890121']]);
        });

        try {
            $missingPreview = (new XlsxSourceParser)->parseFile($missing, ['cid', 'service_key']);
            $duplicatePreview = (new XlsxSourceParser)->parseFile($duplicate, ['cid']);

            $this->assertSame('missing_required_columns', $missingPreview['errors'][0]['code']);
            $this->assertSame('duplicate_recognized_header', $duplicatePreview['errors'][0]['code']);
        } finally {
            @unlink($missing);
            @unlink($duplicate);
        }
    }

    public function test_duplicate_aliases_and_bounded_package_shape_fail_closed(): void
    {
        $duplicate = $this->workbook(function (Spreadsheet $book): void {
            $book->getActiveSheet()->fromArray([
                ['cid', 'service_key', 'service'],
                [null, 'SYN_ALPHA', 'SYN_ALPHA'],
            ]);
            $book->getActiveSheet()->setCellValueExplicit('A2', '1234567890121', DataType::TYPE_STRING);
        });
        $wide = $this->workbook(function (Spreadsheet $book): void {
            $book->getActiveSheet()->setCellValue('BM1', 'too-wide');
        });
        $tall = $this->workbook(function (Spreadsheet $book): void {
            $book->getActiveSheet()->setCellValue('A10002', 'too-tall');
        });
        $unsafeZip = tempnam(sys_get_temp_dir(), 'xlsx_unsafe_zip_');
        $this->assertIsString($unsafeZip);
        $zip = new \ZipArchive;
        $this->assertTrue($zip->open($unsafeZip) === true);
        $zip->addFromString('../traversal.xml', 'synthetic');
        $zip->close();

        try {
            $this->assertSame('duplicate_recognized_header', (new XlsxSourceParser)->parseFile($duplicate)['errors'][0]['code']);
            $this->assertSame('xlsx_column_limit_exceeded', (new XlsxSourceParser)->parseFile($wide)['errors'][0]['code']);
            $this->assertSame('xlsx_row_limit_exceeded', (new XlsxSourceParser)->parseFile($tall)['errors'][0]['code']);
            $this->assertSame('xlsx_zip_path_rejected', (new XlsxSourceParser)->parseFile($unsafeZip)['errors'][0]['code']);
        } finally {
            @unlink($duplicate);
            @unlink($wide);
            @unlink($tall);
            @unlink($unsafeZip);
        }
    }

    public function test_date_formatted_numeric_source_cell_is_not_coerced(): void
    {
        $path = $this->workbook(function (Spreadsheet $book): void {
            $sheet = $book->getActiveSheet();
            $sheet->fromArray([['cid', 'service_key'], ['1234567890121', 45678]]);
            $sheet->getStyle('B2')->getNumberFormat()->setFormatCode(NumberFormat::FORMAT_DATE_YYYYMMDD);
        });

        try {
            $preview = (new XlsxSourceParser)->parseFile($path, ['cid', 'service_key']);
            $this->assertSame('xlsx_date_coercion_rejected', $preview['errors'][0]['code']);
        } finally {
            @unlink($path);
        }
    }

    /** @param callable(Spreadsheet): void $configure */
    private function workbook(callable $configure): string
    {
        $book = new Spreadsheet;
        $configure($book);
        $path = tempnam(sys_get_temp_dir(), 'xlsx_source_test_');
        $this->assertIsString($path);
        (new Xlsx($book))->save($path);
        $book->disconnectWorksheets();

        return $path;
    }
}
