<?php

namespace App\Services\Import;

use Illuminate\Support\Facades\DB;
use LogicException;

final class StagingImportService
{
    public function createPreview(array $files): array
    {
        throw new LogicException('W4 import staging is not implemented in W0-W2.');
    }

    public function persistSourcePreview(array $preview, array $context = []): array
    {
        $this->assertPersistablePreview($preview);
        $sha256 = $context['sha256'] ?? $this->previewHash('source', $preview, $context);

        if (DB::table('source_import_files')->where('sha256', $sha256)->exists()) {
            throw new LogicException('Synthetic source preview was already staged.');
        }

        return DB::transaction(function () use ($preview, $context, $sha256): array {
            $now = now();
            $jobId = DB::table('source_import_jobs')->insertGetId([
                'job_name' => $context['job_name'] ?? 'Synthetic source preview',
                'status' => 'preview_staged',
                'total_files' => 1,
                'total_rows' => $preview['total_rows'],
                'valid_rows' => $preview['valid_rows'],
                'invalid_rows' => $preview['invalid_rows'] + $preview['missing_identifier_rows'],
                'review_rows' => $preview['invalid_rows'] + $preview['missing_identifier_rows'],
                'error_message' => null,
                'started_at' => null,
                'finished_at' => null,
                'created_at' => $now,
                'updated_at' => $now,
            ]);

            $fileId = DB::table('source_import_files')->insertGetId([
                'source_import_job_id' => $jobId,
                'original_filename' => $context['original_filename'] ?? 'synthetic-preview.csv',
                'stored_path' => '__synthetic_preview_no_file_stored__',
                'mime_type' => 'text/csv',
                'size_bytes' => 0,
                'sha256' => $sha256,
                'sheet_count' => null,
                'row_count' => $preview['total_rows'],
                'created_at' => $now,
                'updated_at' => $now,
            ]);

            foreach ($preview['rows'] as $row) {
                $this->assertPersistableRow($row);
                $rawPayload = $row['raw_payload'];

                DB::table('source_import_rows')->insert([
                    'source_import_job_id' => $jobId,
                    'source_file_id' => $fileId,
                    'sheet_name' => $context['sheet_name'] ?? null,
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

            return [
                'source_import_job_id' => $jobId,
                'source_file_id' => $fileId,
                'sha256' => $sha256,
                'rows_inserted' => $preview['total_rows'],
                'status' => 'preview_staged',
            ];
        });
    }

    public function persistTargetGroupPreview(array $preview, array $context = []): array
    {
        $this->assertPersistablePreview($preview);
        $sha256 = $context['sha256'] ?? $this->previewHash('target_group', $preview, $context);

        if (DB::table('target_group_files')->where('sha256', $sha256)->exists()) {
            throw new LogicException('Synthetic target group preview was already staged.');
        }

        return DB::transaction(function () use ($preview, $context, $sha256): array {
            $now = now();
            $jobId = DB::table('target_group_jobs')->insertGetId([
                'group_name' => $context['group_name'] ?? 'Synthetic target group preview',
                'status' => 'preview_staged',
                'total_files' => 1,
                'total_rows' => $preview['total_rows'],
                'valid_rows' => $preview['valid_rows'],
                'invalid_rows' => $preview['invalid_rows'] + $preview['missing_identifier_rows'],
                'review_rows' => $preview['invalid_rows'] + $preview['missing_identifier_rows'],
                'source_set_hash' => $sha256,
                'error_message' => null,
                'started_at' => null,
                'finished_at' => null,
                'created_at' => $now,
                'updated_at' => $now,
            ]);

            $fileId = DB::table('target_group_files')->insertGetId([
                'target_group_job_id' => $jobId,
                'original_filename' => $context['original_filename'] ?? 'synthetic-preview.csv',
                'stored_path' => '__synthetic_preview_no_file_stored__',
                'mime_type' => 'text/csv',
                'size_bytes' => 0,
                'sha256' => $sha256,
                'sheet_count' => null,
                'row_count' => $preview['total_rows'],
                'created_at' => $now,
                'updated_at' => $now,
            ]);

            foreach ($preview['rows'] as $row) {
                $this->assertPersistableRow($row);
                $rawPayload = $row['raw_payload'];

                DB::table('target_group_rows')->insert([
                    'target_group_job_id' => $jobId,
                    'target_group_file_id' => $fileId,
                    'sheet_name' => $context['sheet_name'] ?? null,
                    'row_number' => $row['row_number'],
                    'raw_payload' => json_encode($rawPayload),
                    'raw_cid' => $row['raw_cid'] ?? null,
                    'normalized_cid' => $row['normalized_cid'] ?? null,
                    'cid_status' => $row['identifier_status'],
                    'raw_full_name' => $rawPayload['full_name'] ?? $rawPayload['name'] ?? null,
                    'normalized_full_name' => null,
                    'raw_birth_date' => $rawPayload['birth_date'] ?? null,
                    'normalized_birth_date' => null,
                    'validation_status' => $row['validation_status'],
                    'review_reason' => $this->reviewReason($row['validation_status']),
                    'created_at' => $now,
                    'updated_at' => $now,
                ]);
            }

            return [
                'target_group_job_id' => $jobId,
                'target_group_file_id' => $fileId,
                'sha256' => $sha256,
                'rows_inserted' => $preview['total_rows'],
                'status' => 'preview_staged',
            ];
        });
    }

    private function assertPersistablePreview(array $preview): void
    {
        if (($preview['errors'] ?? []) !== []) {
            throw new LogicException('Preview with errors cannot be staged.');
        }

        foreach (['total_rows', 'valid_rows', 'invalid_rows', 'missing_identifier_rows', 'rows'] as $key) {
            if (! array_key_exists($key, $preview)) {
                throw new LogicException("Malformed preview is missing {$key}.");
            }
        }
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

    private function previewHash(string $scope, array $preview, array $context): string
    {
        return hash('sha256', json_encode([
            'scope' => $scope,
            'preview' => $preview,
            'context' => $context,
        ]));
    }

    private function reviewReason(string $validationStatus): ?string
    {
        return match ($validationStatus) {
            'valid' => null,
            'invalid_identifier' => 'CID failed validation in preview.',
            'missing_identifier' => 'CID is missing in preview.',
            default => 'Preview row requires review.',
        };
    }
}
