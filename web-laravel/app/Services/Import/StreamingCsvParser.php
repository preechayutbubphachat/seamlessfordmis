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
     * Confirmed target-group header aliases (from discovery contract)
     * @var array<string, list<string>>
     */
    private const TARGET_GROUP_HEADER_ALIASES = [
        'cid' => ['cid'],
        'full_name' => ['full_name', 'name'],
        'birth_date' => ['birth_date'],
        'service_key' => ['service_key', 'service'],
        'service_date' => ['service_date', 'visit_date'],
    ];

    /**
     * Confirmed source import header aliases (from discovery contract)
     * @var array<string, list<string>>
     */
    private const SOURCE_IMPORT_HEADER_ALIASES = [
        'cid' => ['cid'],
        'service_key' => ['service_key', 'service'],
        'service_date' => ['service_date', 'visit_date'],
        'status' => ['status'],
    ];

    /**
     * @param list<string> $requiredColumns
     * @param string $importType 'source' | 'target_group'
     * @return array{
     *     total_rows: int,
     *     valid_rows: int,
     *     invalid_rows: int,
     *     missing_identifier_rows: int,
     *     errors: list<array<string, mixed>>,
     *     warnings: list<array<string, mixed>>,
     *     rows: list<array<string, mixed>>,
     *     header_mapping: array<string, string|null>
     * }
     */
    public function parseFile(string $path, array $requiredColumns = ['cid'], string $importType = 'source'): array
    {
        if (!is_file($path) || !is_readable($path)) {
            return $this->emptyPreview([[
                'code' => 'file_not_readable',
                'message' => 'CSV file is not readable.',
            ]], $requiredColumns);
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
            ]], $requiredColumns);
        }

        try {
            $headers = $reader->getHeader();
        } catch (\Throwable) {
            return $this->emptyPreview([[
                'code' => 'missing_header',
                'message' => 'CSV header row is required.',
            ]], $requiredColumns);
        }

        if ($headers === null || $headers === []) {
            return $this->emptyPreview([[
                'code' => 'missing_header',
                'message' => 'CSV header row is required.',
            ]], $requiredColumns);
        }

        $normalizedHeaders = $this->normalizeHeaders($headers);

        // Get header aliases for the import type
        $headerAliases = $importType === 'target_group'
            ? self::TARGET_GROUP_HEADER_ALIASES
            : self::SOURCE_IMPORT_HEADER_ALIASES;

        // Map headers to canonical fields
        $headerMapping = $this->mapHeaders($normalizedHeaders, $headerAliases);

        $recognizedHeaderCounts = [];
        foreach ($headerMapping as $canonicalField) {
            if ($canonicalField !== null) {
                $recognizedHeaderCounts[$canonicalField] = ($recognizedHeaderCounts[$canonicalField] ?? 0) + 1;
            }
        }

        $duplicateCanonicalHeaders = array_keys(array_filter(
            $recognizedHeaderCounts,
            static fn (int $count): bool => $count > 1,
        ));

        if ($duplicateCanonicalHeaders !== []) {
            return $this->emptyPreview([[
                'code' => 'duplicate_recognized_header',
                'columns' => $duplicateCanonicalHeaders,
                'message' => 'A recognized CSV header is duplicated and cannot be mapped unambiguously.',
            ]], $requiredColumns, $headerMapping);
        }

        // Check required columns (using canonical field names)
        $canonicalHeaders = array_values(array_unique(array_filter($headerMapping, fn ($v) => $v !== null)));
        $missingColumns = array_values(array_diff($requiredColumns, $canonicalHeaders));

        if ($missingColumns !== []) {
            return $this->emptyPreview([[
                'code' => 'missing_required_columns',
                'columns' => $missingColumns,
                'message' => 'Required columns are missing.',
            ]], $requiredColumns, $headerMapping);
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

            // Map to canonical field names
            $canonicalPayload = $this->mapToCanonical($rawPayload, $headerMapping);

            $identifier = $validator->validate($canonicalPayload['cid'] ?? null);

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
                'raw_cid' => $canonicalPayload['cid'] ?? null,
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
            'header_mapping' => $headerMapping,
        ];
    }

    /**
     * @param list<string> $requiredColumns
     * @param string $importType 'source' | 'target_group'
     * @return array{
     *     total_rows: int,
     *     valid_rows: int,
     *     invalid_rows: int,
     *     missing_identifier_rows: int,
     *     errors: list<array<string, mixed>>,
     *     warnings: list<array<string, mixed>>,
     *     rows: list<array<string, mixed>>,
     *     header_mapping: array<string, string|null>
     * }
     */
    public function parseString(string $csvContent, array $requiredColumns = ['cid'], string $importType = 'source'): array
    {
        // For backward compatibility - write to temp file and parse
        $tempPath = tempnam(sys_get_temp_dir(), 'csv_preview_');
        if ($tempPath === false) {
            return $this->emptyPreview([[
                'code' => 'temp_file_failed',
                'message' => 'Failed to create temporary file.',
            ]], $requiredColumns, [], $importType);
        }

        try {
            file_put_contents($tempPath, $csvContent);
            return $this->parseFile($tempPath, $requiredColumns, $importType);
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
     * Map normalized headers to canonical fields using aliases
     * @param list<string> $normalizedHeaders
     * @param array<string, list<string>> $headerAliases
     * @return array<string, string|null>
     */
    private function mapHeaders(array $normalizedHeaders, array $headerAliases): array
    {
        $mapping = [];
        foreach ($normalizedHeaders as $header) {
            $canonical = null;
            foreach ($headerAliases as $canonField => $aliases) {
                if (in_array($header, $aliases, true)) {
                    $canonical = $canonField;
                    break;
                }
            }
            $mapping[$header] = $canonical;
        }
        return $mapping;
    }

    /**
     * Map raw payload to canonical field names
     * @param array<string, string> $rawPayload
     * @param array<string, string|null> $headerMapping
     * @return array<string, string>
     */
    private function mapToCanonical(array $rawPayload, array $headerMapping): array
    {
        $canonical = [];
        foreach ($rawPayload as $header => $value) {
            $canonicalField = $headerMapping[$header] ?? null;
            if ($canonicalField !== null) {
                $canonical[$canonicalField] = $value;
            }
        }
        return $canonical;
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
     * @param list<string> $requiredColumns
     * @param array<string, string|null> $headerMapping
     * @return array{
     *     total_rows: int,
     *     valid_rows: int,
     *     invalid_rows: int,
     *     missing_identifier_rows: int,
     *     errors: list<array<string, mixed>>,
     *     warnings: list<array<string, mixed>>,
     *     rows: list<array<string, mixed>>,
     *     header_mapping: array<string, string|null>
     * }
     */
    private function emptyPreview(array $errors, array $requiredColumns = ['cid'], array $headerMapping = [], string $importType = 'source'): array
    {
        return [
            'total_rows' => 0,
            'valid_rows' => 0,
            'invalid_rows' => 0,
            'missing_identifier_rows' => 0,
            'errors' => $errors,
            'warnings' => [],
            'rows' => [],
            'header_mapping' => $headerMapping,
        ];
    }
}