<?php

namespace App\Services\Import;

use App\Services\CidValidator;

final class CsvPreviewParser
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
    public function parseString(string $csvContent, array $requiredColumns = ['cid']): array
    {
        $lines = $this->nonEmptyLines($csvContent);

        if ($lines === []) {
            return $this->emptyPreview([
                [
                    'code' => 'missing_header',
                    'message' => 'CSV header row is required for preview.',
                ],
            ]);
        }

        $headers = $this->normalizeHeaders(str_getcsv($lines[0]));
        $missingColumns = array_values(array_diff($requiredColumns, $headers));

        if ($missingColumns !== []) {
            return $this->emptyPreview([
                [
                    'code' => 'missing_required_columns',
                    'columns' => $missingColumns,
                    'message' => 'Required columns are missing.',
                ],
            ]);
        }

        $rows = [];
        $validRows = 0;
        $invalidRows = 0;
        $missingIdentifierRows = 0;
        $validator = new CidValidator();

        foreach (array_slice($lines, 1) as $offset => $line) {
            $rowNumber = $offset + 2;
            $rawPayload = $this->combineRow($headers, str_getcsv($line));
            $identifier = $validator->validate($rawPayload['cid'] ?? null);

            if ($identifier['status'] === CidValidator::STATUS_VALID) {
                $validRows++;
            } elseif ($identifier['status'] === CidValidator::STATUS_MISSING) {
                $missingIdentifierRows++;
            } else {
                $invalidRows++;
            }

            $rows[] = [
                'row_number' => $rowNumber,
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
        return $this->parseString((string) file_get_contents($path), $requiredColumns);
    }

    /**
     * @return list<string>
     */
    private function nonEmptyLines(string $csvContent): array
    {
        return array_values(array_filter(
            preg_split('/\r\n|\r|\n/', $csvContent) ?: [],
            fn (string $line): bool => trim($line) !== ''
        ));
    }

    /**
     * @param list<string|null> $headers
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
     * @param list<string|null> $values
     * @return array<string, string>
     */
    private function combineRow(array $headers, array $values): array
    {
        $row = [];

        foreach ($headers as $index => $header) {
            $row[$header] = trim((string) ($values[$index] ?? ''));
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
