<?php

namespace App\Services\Import;

use App\Services\Audit\AuditLogger;
use App\Services\FileHashService;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use InvalidArgumentException;
use LogicException;

final class SourceImportService
{
    public function __construct(
        private readonly StreamingCsvParser $csvParser = new StreamingCsvParser,
        private readonly XlsxSourceParser $xlsxParser = new XlsxSourceParser,
        private readonly FileHashService $fileHashService = new FileHashService,
        private readonly AuditLogger $auditLogger = new AuditLogger,
    ) {}

    /**
     * Stage a full source import from uploaded files.
     *
     * @param  list<UploadedFile>  $files
     * @return array{
     *     source_import_job_id: int,
     *     source_file_ids: list<int>,
     *     sha256: list<string>,
     *     rows_inserted: int,
     *     status: string,
     *     reconciliation: array<string, int>
     * }
     */
    public function stage(array $files): array
    {
        if ($files === []) {
            throw new InvalidArgumentException('At least one file must be provided.');
        }

        // Validate all files before any persistence
        $validatedFiles = $this->validateFiles($files);

        // Check for duplicates across all files first
        $sha256List = array_column($validatedFiles, 'sha256');
        $existingShas = DB::table('source_import_files')
            ->whereIn('sha256', $sha256List)
            ->pluck('sha256')
            ->toArray();

        if ($existingShas !== []) {
            throw new LogicException(
                'Duplicate file(s) detected: '.implode(', ', $existingShas).
                '. These files have already been imported.'
            );
        }

        // Process all files in a single transaction
        return DB::transaction(function () use ($validatedFiles, $sha256List): array {
            $now = now();
            $sourceFileIds = [];
            $totalRows = 0;
            $totalValidRows = 0;
            $totalInvalidRows = 0;
            $totalMissingIdentifierRows = 0;
            $allRows = [];

            // Create the import job
            $jobId = DB::table('source_import_jobs')->insertGetId([
                'job_name' => 'Full source import - '.$now->format('Y-m-d H:i:s'),
                'status' => 'processing',
                'total_files' => count($validatedFiles),
                'total_rows' => 0,
                'valid_rows' => 0,
                'invalid_rows' => 0,
                'review_rows' => 0,
                'error_message' => null,
                'started_at' => $now,
                'finished_at' => null,
                'created_at' => $now,
                'updated_at' => $now,
            ]);

            foreach ($validatedFiles as $fileData) {
                $fileId = DB::table('source_import_files')->insertGetId([
                    'source_import_job_id' => $jobId,
                    'original_filename' => $fileData['original_filename'],
                    'stored_path' => $fileData['stored_path'],
                    'mime_type' => $fileData['mime_type'],
                    'size_bytes' => $fileData['size_bytes'],
                    'sha256' => $fileData['sha256'],
                    'sheet_count' => 1,
                    'row_count' => $fileData['preview']['total_rows'],
                    'created_at' => $now,
                    'updated_at' => $now,
                ]);

                $sourceFileIds[] = $fileId;

                // Persist all rows for this file
                foreach ($fileData['preview']['rows'] as $row) {
                    $this->assertPersistableRow($row);

                    $rawPayload = $row['raw_payload'];

                    DB::table('source_import_rows')->insert([
                        'source_import_job_id' => $jobId,
                        'source_file_id' => $fileId,
                        'sheet_name' => null,
                        'row_number' => $row['row_number'],
                        'raw_payload' => json_encode($rawPayload),
                        'raw_cid' => $row['raw_cid'] ?? null,
                        'normalized_cid' => $row['normalized_cid'] ?? null,
                        'cid_status' => $row['identifier_status'],
                        'raw_full_name' => $rawPayload['full_name'] ?? $rawPayload['name'] ?? null,
                        'normalized_full_name' => null,
                        'raw_service_text' => $rawPayload['service_key'] ?? $rawPayload['service'] ?? null,
                        'normalized_service_key' => $rawPayload['service_key'] ?? null,
                        'raw_visit_date' => $rawPayload['service_date'] ?? $rawPayload['visit_date'] ?? null,
                        'normalized_visit_date' => null,
                        'validation_status' => $row['validation_status'],
                        'review_reason' => $this->reviewReason($row['validation_status']),
                        'created_at' => $now,
                        'updated_at' => $now,
                    ]);
                }

                $totalRows += $fileData['preview']['total_rows'];
                $totalValidRows += $fileData['preview']['valid_rows'];
                $totalInvalidRows += $fileData['preview']['invalid_rows'];
                $totalMissingIdentifierRows += $fileData['preview']['missing_identifier_rows'];
            }

            // Update job with totals and mark completed
            $reconciliation = [
                'total_rows' => $totalRows,
                'valid_rows' => $totalValidRows,
                'invalid_rows' => $totalInvalidRows,
                'missing_identifier_rows' => $totalMissingIdentifierRows,
                'review_rows' => $totalInvalidRows + $totalMissingIdentifierRows,
            ];

            DB::table('source_import_jobs')->where('id', $jobId)->update([
                'total_rows' => $totalRows,
                'valid_rows' => $totalValidRows,
                'invalid_rows' => $totalInvalidRows,
                'review_rows' => $totalInvalidRows + $totalMissingIdentifierRows,
                'status' => 'completed',
                'finished_at' => now(),
                'updated_at' => now(),
            ]);

            // Audit log
            $this->auditLogger->log('source_import_staged', 'source_import_job', $jobId, [
                'after_payload' => array_merge([
                    'import_type' => 'source',
                    'sha256' => $sha256List,
                    'rows_inserted' => $totalRows,
                ], $reconciliation),
            ]);

            return [
                'source_import_job_id' => $jobId,
                'source_file_ids' => $sourceFileIds,
                'sha256' => $sha256List,
                'rows_inserted' => $totalRows,
                'status' => 'completed',
                'reconciliation' => $reconciliation,
            ];
        });
    }

    /**
     * @param  list<UploadedFile>  $files
     * @return list<array{
     *     original_filename: string,
     *     stored_path: string,
     *     mime_type: string,
     *     size_bytes: int,
     *     sha256: string,
     *     preview: array{
     *         total_rows: int,
     *         valid_rows: int,
     *         invalid_rows: int,
     *         missing_identifier_rows: int,
     *         errors: list<array<string, mixed>>,
     *         warnings: list<array<string, mixed>>,
     *         rows: list<array<string, mixed>>
     *     }
     * }>
     */
    private function validateFiles(array $files): array
    {
        $validated = [];

        foreach ($files as $file) {
            if (! $file->isValid()) {
                throw new InvalidArgumentException('Uploaded file is not valid: '.$file->getErrorMessage());
            }

            $originalFilename = $file->getClientOriginalName();
            $mimeType = $file->getMimeType();
            $size = $file->getSize();

            // Enforce bounded source file types.
            $extension = strtolower(pathinfo($originalFilename, PATHINFO_EXTENSION));
            $isCsv = in_array($mimeType, ['text/csv', 'text/plain', 'application/csv'], true) && $extension === 'csv';
            $isXlsx = $mimeType === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' && $extension === 'xlsx';
            if (! $isCsv && ! $isXlsx) {
                throw new InvalidArgumentException('File type not allowed: '.$mimeType.'. Only CSV or bounded XLSX source files are accepted.');
            }

            // Enforce max size (10MB default)
            if ($size > 10 * 1024 * 1024) {
                throw new InvalidArgumentException('File size exceeds maximum allowed (10MB): '.$originalFilename);
            }

            // Store temporarily
            $storedPath = $file->store('imports/temp', 'local');

            // Calculate SHA256
            $sha256 = $this->fileHashService->sha256(Storage::disk('local')->path($storedPath));

            // Parse for preview/validation through the shared source contract.
            $storedAbsolutePath = Storage::disk('local')->path($storedPath);
            $preview = $isXlsx
                ? $this->xlsxParser->parseFile($storedAbsolutePath, ['cid'])
                : $this->csvParser->parseFile($storedAbsolutePath, ['cid']);

            if ($preview['errors'] !== []) {
                Storage::disk('local')->delete($storedPath);
                throw new LogicException('Source file validation failed: '.json_encode($preview['errors']));
            }

            $validated[] = [
                'original_filename' => $originalFilename,
                'stored_path' => $storedPath,
                'mime_type' => $mimeType,
                'size_bytes' => $size,
                'sha256' => $sha256,
                'preview' => $preview,
            ];
        }

        return $validated;
    }

    private function assertPersistableRow(array $row): void
    {
        foreach (['row_number', 'raw_payload', 'identifier_status', 'validation_status'] as $key) {
            if (! array_key_exists($key, $row)) {
                throw new LogicException("Malformed preview row is missing {$key}.");
            }
        }

        if (! is_array($row['raw_payload'])) {
            throw new LogicException('Malformed preview row raw_payload must be an array.');
        }
    }

    private function reviewReason(string $validationStatus): ?string
    {
        return match ($validationStatus) {
            'valid' => null,
            'invalid_identifier' => 'CID failed validation.',
            'missing_identifier' => 'CID is missing.',
            default => 'Row requires review.',
        };
    }
}
