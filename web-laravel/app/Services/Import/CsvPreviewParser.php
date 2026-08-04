<?php

namespace App\Services\Import;

use App\Services\CidValidator;

/**
 * CsvPreviewParser - Backward compatible wrapper around StreamingCsvParser
 * Maintains the same public API while using the robust streaming parser internally
 */
final class CsvPreviewParser
{
    private StreamingCsvParser $streamingParser;

    public function __construct()
    {
        $this->streamingParser = new StreamingCsvParser();
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
        return $this->streamingParser->parseString($csvContent, $requiredColumns);
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
    public function parseFile(string $path, array $requiredColumns = ['cid']): array
    {
        return $this->streamingParser->parseFile($path, $requiredColumns);
    }
}