<?php

namespace App\Services\Export;

use App\Models\ExportJob;
use App\Services\Audit\AuditLogger;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

final class DownloadPrivateCsvArtifact
{
    public function __construct(private readonly AuditLogger $auditLogger) {}

    public function forOwner(ExportJob $exportJob, Request $request): Response
    {
        abort_unless((int) $exportJob->requested_by_user_id === (int) $request->user()->id, 403);

        $filename = $exportJob->generated_filename;
        $storedPath = $exportJob->stored_path;
        $expectedDirectory = realpath(storage_path('app/exports'));
        $metadataIsValid = $exportJob->status === 'completed'
            && is_string($filename)
            && $filename !== ''
            && basename($filename) === $filename
            && str_ends_with(strtolower($filename), '.csv')
            && $exportJob->mime_type === 'text/csv'
            && is_string($storedPath)
            && $storedPath === 'exports/'.$filename
            && is_int($exportJob->byte_count)
            && $exportJob->byte_count >= 0
            && is_string($exportJob->sha256)
            && preg_match('/^[a-f0-9]{64}$/D', $exportJob->sha256) === 1
            && is_string($expectedDirectory);
        $path = $metadataIsValid ? storage_path('app/'.$storedPath) : null;
        $realPath = is_string($path) ? realpath($path) : false;
        $artifactIsValid = $metadataIsValid
            && is_string($realPath)
            && dirname($realPath) === $expectedDirectory
            && ! is_link($path)
            && is_file($realPath)
            && filesize($realPath) === $exportJob->byte_count
            && hash_equals($exportJob->sha256, (string) hash_file('sha256', $realPath));

        if (! $artifactIsValid) {
            return response('Export artifact is unavailable.', 409, [
                'Content-Type' => 'text/plain; charset=UTF-8',
                'X-Content-Type-Options' => 'nosniff',
            ]);
        }

        $this->auditLogger->log('export_csv_downloaded', 'export_job', $exportJob->id, [
            'actor_user_id' => $request->user()->id,
            'ip_address' => $request->ip(),
            'user_agent' => $request->userAgent(),
            'after_payload' => [
                'byte_count' => $exportJob->byte_count,
                'sha256' => $exportJob->sha256,
            ],
        ]);

        return response()->download($realPath, $filename, [
            'Content-Type' => 'text/csv',
            'X-Content-Type-Options' => 'nosniff',
        ]);
    }
}
