<?php

namespace App\Services\Import;

use PhpOffice\PhpSpreadsheet\Cell\Coordinate;
use PhpOffice\PhpSpreadsheet\Cell\DataType;
use PhpOffice\PhpSpreadsheet\Reader\Xlsx;
use PhpOffice\PhpSpreadsheet\Shared\Date;
use PhpOffice\PhpSpreadsheet\Worksheet\Worksheet;
use ZipArchive;

final class XlsxSourceParser
{
    private const MAX_ZIP_ENTRIES = 256;

    private const MAX_TOTAL_UNCOMPRESSED_BYTES = 20 * 1024 * 1024;

    private const MAX_SINGLE_ENTRY_UNCOMPRESSED_BYTES = 10 * 1024 * 1024;

    private const MAX_DATA_ROWS = 10000;

    private const MAX_COLUMNS = 64;

    public function __construct(
        private readonly StreamingCsvParser $csvParser = new StreamingCsvParser,
    ) {}

    /**
     * @param  list<string>  $requiredColumns
     * @return array<string, mixed>
     */
    public function parseFile(string $path, array $requiredColumns = ['cid'], string $importType = 'source'): array
    {
        if ($importType !== 'source') {
            return $this->error('xlsx_source_only', 'XLSX source import is the only supported XLSX workflow.');
        }

        if (! is_file($path) || ! is_readable($path)) {
            return $this->error('file_not_readable', 'XLSX file is not readable.');
        }

        $packageError = $this->validateZipPackage($path);
        if ($packageError !== null) {
            return $this->error($packageError['code'], $packageError['message']);
        }

        $csvPath = tempnam(sys_get_temp_dir(), 'xlsx_source_csv_');
        if ($csvPath === false) {
            return $this->error('temp_file_failed', 'Failed to create a bounded temporary preview file.');
        }

        try {
            $reader = new Xlsx;
            $reader->setReadDataOnly(false);
            $reader->setReadEmptyCells(true);
            $reader->setIncludeCharts(false);
            $reader->setAllowExternalImages(false);

            $spreadsheet = $reader->load($path);
            $worksheetCount = $spreadsheet->getSheetCount();
            $visibleSheets = array_values(array_filter(
                $spreadsheet->getAllSheets(),
                static fn (Worksheet $sheet): bool => $sheet->getSheetState() === Worksheet::SHEETSTATE_VISIBLE,
            ));

            if ($worksheetCount !== 1) {
                return $this->error('xlsx_single_sheet_required', 'Workbook must contain exactly one worksheet.');
            }

            if (count($visibleSheets) !== 1) {
                return $this->error('xlsx_visible_sheet_required', 'Workbook worksheet must be visible.');
            }

            $sheet = $visibleSheets[0];
            $highestRow = $sheet->getHighestRow();
            $highestColumn = $sheet->getHighestColumn();
            $highestColumnIndex = Coordinate::columnIndexFromString($highestColumn);

            if ($highestRow > self::MAX_DATA_ROWS + 1) {
                return $this->error('xlsx_row_limit_exceeded', 'Workbook exceeds the maximum of 10000 data rows.');
            }

            if ($highestColumnIndex > self::MAX_COLUMNS) {
                return $this->error('xlsx_column_limit_exceeded', 'Workbook exceeds the maximum of 64 columns.');
            }

            $matrix = [];
            $cidColumn = null;

            for ($row = 1; $row <= $highestRow; $row++) {
                $values = [];
                for ($column = 1; $column <= $highestColumnIndex; $column++) {
                    $cell = $sheet->getCell(Coordinate::stringFromColumnIndex($column).$row);
                    if ($cell->getDataType() === DataType::TYPE_FORMULA || $cell->isFormula()) {
                        return $this->error('xlsx_formula_rejected', 'Formula cells are not accepted in source import workbooks.');
                    }

                    if ($row > 1 && $cell->getDataType() === DataType::TYPE_NUMERIC
                        && Date::isDateTimeFormatCode($cell->getStyle()->getNumberFormat()->getFormatCode())) {
                        return $this->error('xlsx_date_coercion_rejected', 'Date-formatted numeric cells cannot be coerced into source text.');
                    }

                    $value = $this->textValue($cell->getValue());
                    if ($row === 1) {
                        $value = strtolower(trim($value, " \t\n\r\0\x0B\xEF\xBB\BF"));
                    }
                    $values[] = $value;

                    if ($row === 1 && strtolower(trim($value, " \t\n\r\0\x0B\xEF\xBB\BF")) === 'cid') {
                        $cidColumn ??= $column;
                    }
                }
                $matrix[] = $values;
            }

            $recognizedHeaderCounts = [];
            foreach ($matrix[0] ?? [] as $header) {
                $canonical = match ($header) {
                    'cid' => 'cid',
                    'service_key', 'service' => 'service_key',
                    'service_date', 'visit_date' => 'service_date',
                    'status' => 'status',
                    default => null,
                };
                if ($canonical !== null) {
                    $recognizedHeaderCounts[$canonical] = ($recognizedHeaderCounts[$canonical] ?? 0) + 1;
                }
            }
            $duplicateCanonicalHeaders = array_keys(array_filter(
                $recognizedHeaderCounts,
                static fn (int $count): bool => $count > 1,
            ));
            if ($duplicateCanonicalHeaders !== []) {
                return $this->error('duplicate_recognized_header', 'A recognized source header is duplicated.');
            }

            if ($cidColumn === null) {
                $header = array_map(
                    static fn (string $value): string => strtolower(trim($value, " \t\n\r\0\x0B\xEF\xBB\BF")),
                    $matrix[0] ?? [],
                );
                $headerMapping = [];
                foreach ($header as $value) {
                    $headerMapping[$value] = in_array($value, ['service_key', 'service', 'service_date', 'visit_date', 'status'], true)
                        ? $value
                        : null;
                }

                return $this->csvParser->parseString($this->toCsv($matrix), $requiredColumns, 'source');
            }

            for ($row = 2; $row <= $highestRow; $row++) {
                $cell = $sheet->getCell(Coordinate::stringFromColumnIndex($cidColumn).$row);
                if ($this->isNonTextCid($cell)) {
                    return $this->error('xlsx_cid_must_be_text', 'CID cells must be stored as exact textual values.');
                }
            }

            return $this->csvParser->parseString($this->toCsv($matrix), $requiredColumns, 'source');
        } catch (\Throwable $exception) {
            return $this->error('xlsx_parse_failed', 'XLSX parsing failed safely: '.$exception->getMessage());
        } finally {
            if (is_file($csvPath)) {
                @unlink($csvPath);
            }
        }
    }

    /** @return array{code: string, message: string}|null */
    private function validateZipPackage(string $path): ?array
    {
        if (! class_exists(ZipArchive::class)) {
            return ['code' => 'xlsx_zip_unavailable', 'message' => 'XLSX ZIP validation is unavailable.'];
        }

        $zip = new ZipArchive;
        if ($zip->open($path) !== true) {
            return ['code' => 'xlsx_malformed_zip', 'message' => 'Malformed XLSX ZIP package.'];
        }

        try {
            if ($zip->numFiles === 0 || $zip->numFiles > self::MAX_ZIP_ENTRIES) {
                return ['code' => 'xlsx_zip_entry_limit_exceeded', 'message' => 'XLSX ZIP entry count is outside the approved bound.'];
            }

            $totalSize = 0;
            for ($index = 0; $index < $zip->numFiles; $index++) {
                $stat = $zip->statIndex($index);
                $name = (string) ($stat['name'] ?? '');
                $size = (int) ($stat['size'] ?? -1);
                $flags = (int) ($stat['flags'] ?? 0);

                if ($name === '' || $this->unsafeZipPath($name)) {
                    return ['code' => 'xlsx_zip_path_rejected', 'message' => 'Unsafe XLSX ZIP member path.'];
                }

                if (($flags & 1) === 1 || (int) ($stat['encryption_method'] ?? 0) !== 0) {
                    return ['code' => 'xlsx_encrypted_rejected', 'message' => 'Encrypted or password-protected XLSX is not accepted.'];
                }

                if ($size < 0 || $size > self::MAX_SINGLE_ENTRY_UNCOMPRESSED_BYTES) {
                    return ['code' => 'xlsx_zip_entry_size_exceeded', 'message' => 'An XLSX ZIP member exceeds the approved size bound.'];
                }

                $totalSize += $size;
                if ($totalSize > self::MAX_TOTAL_UNCOMPRESSED_BYTES) {
                    return ['code' => 'xlsx_zip_total_size_exceeded', 'message' => 'XLSX ZIP total uncompressed size exceeds the approved bound.'];
                }

                if (str_contains(strtolower($name), 'externallink')) {
                    return ['code' => 'xlsx_external_content_rejected', 'message' => 'External workbook links are not accepted.'];
                }

                if (str_ends_with(strtolower($name), '.xml') || str_ends_with(strtolower($name), '.rels')) {
                    $content = $zip->getFromIndex($index);
                    if ($content === false || preg_match('/TargetMode\s*=\s*["\']External|<externalLink\b/i', $content) === 1) {
                        return ['code' => 'xlsx_external_content_rejected', 'message' => 'External workbook resources are not accepted.'];
                    }
                }
            }
        } finally {
            $zip->close();
        }

        return null;
    }

    private function unsafeZipPath(string $name): bool
    {
        $normalized = str_replace('\\', '/', $name);

        return str_starts_with($normalized, '/')
            || preg_match('/^[A-Za-z]:\//', $normalized) === 1
            || in_array('..', explode('/', $normalized), true);
    }

    private function isNonTextCid(object $cell): bool
    {
        return $cell->getDataType() !== DataType::TYPE_STRING
            && $cell->getDataType() !== DataType::TYPE_INLINE;
    }

    private function textValue(mixed $value): string
    {
        if ($value === null) {
            return '';
        }
        if (is_object($value) && method_exists($value, 'getPlainText')) {
            return (string) $value->getPlainText();
        }
        if (is_bool($value)) {
            return $value ? '1' : '0';
        }

        return (string) $value;
    }

    /** @param list<list<string>> $matrix */
    private function toCsv(array $matrix): string
    {
        $stream = fopen('php://temp', 'w+b');
        if ($stream === false) {
            return '';
        }

        foreach ($matrix as $row) {
            fputcsv($stream, $row, ',', '"', '\\');
        }
        rewind($stream);
        $csv = stream_get_contents($stream);
        fclose($stream);

        return is_string($csv) ? $csv : '';
    }

    /** @return array<string, mixed> */
    private function error(string $code, string $message): array
    {
        return [
            'total_rows' => 0,
            'valid_rows' => 0,
            'invalid_rows' => 0,
            'missing_identifier_rows' => 0,
            'errors' => [['code' => $code, 'message' => $message]],
            'warnings' => [],
            'rows' => [],
            'header_mapping' => [],
        ];
    }
}
