<?php

namespace App\Services\Import;

use App\Services\Audit\AuditLogger;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Symfony\Component\HttpFoundation\StreamedResponse;

final class SourceImportErrorExportService
{
    private const HEADER = [
        'source_import_job_id',
        'source_import_row_id',
        'validation_status',
        'error_code',
        'safe_message',
    ];

    private const UTF8_BOM = "\xEF\xBB\xBF";

    private const LINE_ENDING = "\r\n";

    private const FALLBACK_ERROR_CODE = 'SOURCE_ROW_VALIDATION_FAILED';

    private const FALLBACK_SAFE_MESSAGE = 'Row failed source import validation.';

    public function __construct(private readonly AuditLogger $auditLogger) {}

    public function download(int $jobId, int $actorUserId): StreamedResponse
    {
        if (! DB::table('source_import_jobs')->where('id', $jobId)->exists()) {
            abort(404);
        }

        $query = $this->nonValidRowsQuery($jobId);
        $errorCount = (clone $query)->count('source_import_rows.id');

        $this->auditLogger->log('source_import_error_exported', 'source_import_job', $jobId, [
            'actor_user_id' => $actorUserId,
            'after_payload' => [
                'source_import_job_id' => $jobId,
                'exported_error_count' => $errorCount,
                'format' => 'csv',
            ],
        ]);

        return response()->streamDownload(function () use ($query): void {
            $handle = fopen('php://output', 'wb');
            if ($handle === false) {
                throw new RuntimeException('source_import_error_export_stream_open_failed');
            }

            try {
                $this->writeBytes($handle, self::UTF8_BOM);
                $this->writeCsvRow($handle, self::HEADER);

                foreach ($query->cursor() as $row) {
                    $this->writeCsvRow($handle, [
                        (string) $row->source_import_job_id,
                        (string) $row->id,
                        $this->safeCell((string) $row->validation_status),
                        self::FALLBACK_ERROR_CODE,
                        self::FALLBACK_SAFE_MESSAGE,
                    ]);
                }
            } finally {
                fclose($handle);
            }
        }, "source-import-errors-job-{$jobId}.csv", [
            'Content-Type' => 'text/csv; charset=UTF-8',
            'X-Content-Type-Options' => 'nosniff',
        ]);
    }

    private function nonValidRowsQuery(int $jobId)
    {
        return DB::table('source_import_rows')
            ->where('source_import_job_id', $jobId)
            ->where(function ($query): void {
                $query->whereNull('validation_status')
                    ->orWhere('validation_status', '<>', 'valid');
            })
            ->select([
                'source_import_job_id',
                'id',
                'validation_status',
            ])
            ->orderBy('id');
    }

    private function safeCell(string $value): string
    {
        if ($value !== '' && in_array($value[0], ['=', '@', '+', '-'], true)) {
            return "'".$value;
        }

        return $value;
    }

    private function writeCsvRow($handle, array $row): void
    {
        if (fputcsv($handle, $row, ',', '"', '', self::LINE_ENDING) === false) {
            throw new RuntimeException('source_import_error_export_csv_write_failed');
        }
    }

    private function writeBytes($handle, string $bytes): void
    {
        if (fwrite($handle, $bytes) !== strlen($bytes)) {
            throw new RuntimeException('source_import_error_export_stream_write_failed');
        }
    }
}
