<?php

namespace App\Services\Import;

final class ImportPreviewService
{
    public function __construct(
        private readonly CsvPreviewParser $csvPreviewParser = new CsvPreviewParser(),
    ) {
    }

    public function previewCsvString(string $csvContent, array $requiredColumns = ['cid']): array
    {
        return $this->csvPreviewParser->parseString($csvContent, $requiredColumns);
    }

    public function previewCsvFile(string $path, array $requiredColumns = ['cid']): array
    {
        return $this->csvPreviewParser->parseFile($path, $requiredColumns);
    }
}
