<?php

namespace App\Services\Import;

final class ImportPreviewService
{
    public function __construct(
        private readonly CsvPreviewParser $csvPreviewParser = new CsvPreviewParser,
        private readonly XlsxSourceParser $xlsxSourceParser = new XlsxSourceParser,
    ) {}

    /**
     * @param  list<string>  $requiredColumns
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
    public function previewCsvString(string $csvContent, array $requiredColumns = ['cid'], string $importType = 'source'): array
    {
        return $this->csvPreviewParser->parseString($csvContent, $requiredColumns, $importType);
    }

    /**
     * @param  list<string>  $requiredColumns
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
    public function previewCsvFile(string $path, array $requiredColumns = ['cid'], string $importType = 'source'): array
    {
        return $this->csvPreviewParser->parseFile($path, $requiredColumns, $importType);
    }

    /**
     * @param  list<string>  $requiredColumns
     * @return array<string, mixed>
     */
    public function previewSourceFile(
        string $path,
        array $requiredColumns = ['cid'],
        ?string $extension = null,
    ): array {
        $extension ??= pathinfo($path, PATHINFO_EXTENSION);

        return strtolower($extension) === 'xlsx'
            ? $this->xlsxSourceParser->parseFile($path, $requiredColumns)
            : $this->csvPreviewParser->parseFile($path, $requiredColumns, 'source');
    }
}
