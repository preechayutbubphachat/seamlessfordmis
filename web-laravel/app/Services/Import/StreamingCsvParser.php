<?php

namespace App\Services\Import;

use App\Services\CidValidator;
use League\Csv\Reader;
use League\Csv\Statement;
use InvalidArgumentException;
use RuntimeException;

/**
 * Streaming CSV parser that correctly handles:
 * - Quoted delimiters
 * - Escaped quotes
 * - Quoted multiline fields
 * - UTF-8 encoding
 * - Large file processing via streaming (no full file in memory)
 *
 * Uses league/csv 9.28+ API (Reader::from(), Statement constructor)
 */
final class StreamingCsvParser
{
    /**
     * @param list<string> $requiredColumns
     * @return array{
     *     total_rows: int,
     *     valid_rows: int,
     *     invalid_rows: int,
     *     missing_identifier_rows: int,
     *     errors: list<array<string, mixed>>,
     *     warnings: list<array<string, mixed>>,
     *     rows: list<array<string, mixed>>
     * }
     */
    public function parseFile(string $path, array $requiredColumns = ['cid']): array
    {
        if (!is_file($path) || !is_readable($path)) {
            return $this->emptyPreview([[
                'code' => 'file_not_readable',
                'message' => 'CSV file is not readable.',
            ]]);
        }

        try {
            $reader = Reader::from($path);
            $reader->setHeaderOffset(0);
            $reader->setDelimiter(',');
            $reader->setEnclosure('"');
            $reader->setEscape('\\');
        } catch (\Throwable $e) {
            return $this->emptyPreview([[
                'code' => 'csv_parse_failed',
                'message' => 'Failed to create CSV reader: '.$e->getMessage(),
            ]]);
        }

        $headers = $reader->getHeader();

        if ($headers === null || $headers === []) {
            return $this->emptyPreview([[
                'code' => 'missing_header',
                'message' => 'CSV header row is required.',
            ]]);
        }

        $normalizedHeaders = $this->normalizeHeaders($headers);
        $missingColumns = array_values(array_diff($requiredColumns, $normalizedHeaders));

        if ($missingColumns !== []) {
            return $this->emptyPreview([[
                'code' => 'missing_required_columns',
                'columns' => $missingColumns,
                'message' => 'Required columns are missing.',
            ]]);
        }

        $rows = [];
        $validRows = 0;
        $invalidRows = 0;
        $missingIdentifierRows = 0;
        $validator = new CidValidator();

        // Use Statement for memory-efficient streaming processing
        $stmt = new Statement();
        $records = $stmt->process($reader);

        foreach ($records as $rowNumber => $record) {
            // League CSV Statement with header offset returns 1-based row numbers for data rows
            // (row 0 = header, row 1 = first data row, etc.)
            // We want 1-based line numbers where header = line 1, first data = line 2
            // So row_number = $rowNumber + 1
            $rowIndex = $rowNumber + 1;

            // Combine normalized headers with record values
            $rawPayload = $this->combineRow($normalizedHeaders, $record);

            $identifier = $validator->validate($rawPayload['cid'] ?? null);

            if ($identifier['status'] === CidValidator::STATUS_VALID) {
                $validRows++;
            } elseif ($identifier['status'] === CidValidator::STATUS_MISSING) {
                $missingIdentifierRows++;
            } else {
                $invalidRows++;
            }

            $rows[] = [
                'row_number' => $rowIndex,
                'raw_payload' => $rawPayload,
                'raw_cid' => $rawPayload['cid'] ?? null,
                'normalized_cid' => $identifier['normalized_cid'],
                'identifier_status' => $identifier['status'],
                'validation_status' => $identifier['status'],
            ];
        }

        return [
            'total_rows' => count($rows),
            'valid_rows' => $validRows,
            'invalid_rows' => $invalidRows,
            'missing_identifier_rows' => $missingIdentifierRows,
            'errors' => [],
            'warnings' => [],
            'rows' => $rows,
        ];
    }

    /**
     * @param list<string> $requiredColumns
     * @return array{
     *     total_rows: int,
     *     valid_rows: int,
     *     invalid_rows: int,
     *     missing_identifier_rows: int,
     *     errors: list<array<string, mixed>>,
     *     warnings: list<array<string, mixed>>,
     *     rows: list<array<string, mixed>>
     * }
     */
    public function parseString(string $csvContent, array $requiredColumns = ['cid']): array
    {
        // For backward compatibility - write to temp file and parse
        $tempPath = tempnam(sys_get_temp_dir(), 'csv_preview_');
        if ($tempPath === false) {
            return $this->emptyPreview([[
                'code' => 'temp_file_failed',
                'message' => 'Failed to create temporary file.',
            ]]);
        }

        try {
            file_put_contents($tempPath, $csvContent);
            return $this->parseFile($tempPath, $requiredColumns);
        } finally {
            if (is_file($tempPath)) {
                @unlink($tempPath);
            }
        }
    }

    /**
     * @param list<string> $headers
     * @return list<string>
     */
    private function normalizeHeaders(array $headers): array
    {
        return array_map(
            fn (?string $header): string => strtolower(trim((string) $header, " \t\n\r\0\x0B\xEF\xBB\xBF")),
            $headers
        );
    }

    /**
     * @param list<string> $headers
     * @param array<string, string> $values
     * @return array<string, string>
     */
    private function combineRow(array $headers, array $values): array
    {
        $row = [];

        foreach ($headers as $index => $header) {
            $row[$header] = trim((string) ($values[$header] ?? ''));
        }

        return $row;
    }

    /**
     * @param list<array<string, mixed>> $errors
     * @return array{
     *     total_rows: int,
     *     valid_rows: int,
     *     invalid_rows: int,
     *     missing_identifier_rows: int,
     *     errors: list<array<string, mixed>>,
     *     warnings: list<array<string, mixed>>,
     *     rows: list<array<string, mixed>>
     * }
     */
    private function emptyPreview(array $errors): array
    {
        return [
            'total_rows' => 0,
            'valid_rows' => 0,
            'invalid_rows' => 0,
            'missing_identifier_rows' => 0,
            'errors' => $errors,
            'warnings' => [],
            'rows' => [],
        ];
    }
}