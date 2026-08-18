<?php

namespace App\Http\Controllers;

use App\Http\Requests\CommitPreviewImportRequest;
use App\Http\Requests\StoreSourceImportRequest;
use App\Http\Requests\PreviewCsvImportRequest;
use App\Services\Audit\AuditLogger;
use App\Services\Import\ImportPreviewService;
use App\Services\Import\SourceImportService;
use App\Services\Import\StagingImportService;
use Carbon\CarbonImmutable;
use Illuminate\Contracts\View\View;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use LogicException;

final class SourceImportController extends Controller
{
    use ImportSafetyResponse;

    private const PREVIEW_TTL_MINUTES = 30;

    public function index(): View
    {
        return view('imports.index', [
            'title' => 'Source Files',
            'jobs' => DB::table('source_import_jobs')
                ->select([
                    'id',
                    'status',
                    'created_by_user_id',
                    'created_at',
                    'total_files',
                    'total_rows',
                    'valid_rows',
                    'invalid_rows',
                    'review_rows',
                ])
                ->orderByDesc('id')
                ->get(),
            'detailRoute' => 'imports.source-files.show',
            'emptyMessage' => 'No staging imports yet',
            'safetyNote' => 'No real patient data. No upload form is available. Source import review is read-only.',
        ]);
    }

    public function show(string $job): View
    {
        $sourceJob = DB::table('source_import_jobs')->where('id', $job)->first();
        $rows = DB::table('source_import_rows')
            ->where('source_import_job_id', $job)
            ->orderBy('row_number')
            ->get();

        return view('imports.show', [
            'title' => 'Source Import Job Detail',
            'job' => $sourceJob,
            'rows' => $rows,
            'emptyMessage' => 'No staged rows yet',
            'legacyEmptyMessage' => 'No records loaded',
            'safetyNote' => 'No real patient data. No upload, parsing, file storage, commit, matching, result generation, or export action is available.',
            'rawFields' => [
                'rawService' => 'raw_service_text',
                'normalizedService' => 'normalized_service_key',
                'rawDate' => 'raw_visit_date',
            ],
        ]);
    }

    public function store(StoreSourceImportRequest $request, SourceImportService $sourceImportService): JsonResponse
    {
        $files = $request->file('files', []);

        // Validate that all files are CSV
        foreach ($files as $file) {
            $extension = strtolower($file->getClientOriginalExtension());
            if ($extension !== 'csv') {
                return $this->importNotEnabled();
            }
        }

        // If no files passed validation, return not enabled
        if ($files === []) {
            return $this->importNotEnabled();
        }

        try {
            $result = $sourceImportService->stage($files);

            return response()->json([
                'message' => 'Source import completed successfully.',
                'source_import_job_id' => $result['source_import_job_id'],
                'source_file_ids' => $result['source_file_ids'],
                'sha256' => $result['sha256'],
                'rows_inserted' => $result['rows_inserted'],
                'status' => $result['status'],
                'reconciliation' => $result['reconciliation'],
                'file_stored' => true,
                'patient_data_imported' => false,
            ]);
        } catch (LogicException $e) {
            return response()->json([
                'message' => $e->getMessage(),
                'file_stored' => false,
                'patient_data_imported' => false,
            ], 422);
        } catch (\InvalidArgumentException $e) {
            return response()->json([
                'message' => $e->getMessage(),
                'file_stored' => false,
                'patient_data_imported' => false,
            ], 422);
        } catch (\Throwable $e) {
            // TEMPORARY: Log the actual exception for debugging
            \Illuminate\Support\Facades\Log::error('SourceImportController::store exception', [
                'class' => get_class($e),
                'message' => $e->getMessage(),
                'file' => $e->getFile(),
                'line' => $e->getLine(),
                'trace' => $e->getTraceAsString(),
            ]);
            // Clean up any temp files on unexpected error
            $this->cleanupTempImports();

            return response()->json([
                'message' => 'Import failed: ' . $e->getMessage(),
                'file_stored' => false,
                'patient_data_imported' => false,
            ], 500);
        }
    }

    public function previewForm(): View
    {
        return view('imports.preview', [
            'title' => 'Source File CSV Preview',
            'postRoute' => 'imports.source-files.preview.store',
            'commitRoute' => 'imports.source-files.preview.commit',
            'importType' => 'source',
            'preview' => null,
            'previewToken' => null,
            'safetyNote' => 'Preview-only for synthetic/dev CSV. No file is stored and no staging rows are inserted.',
        ]);
    }

    public function preview(PreviewCsvImportRequest $request, ImportPreviewService $previewService): View
    {
        $file = $request->file('file');
        $path = (string) $file->getRealPath();
        $preview = $previewService->previewCsvFile($path, ['cid']);
        $sha256 = hash_file('sha256', $path);
        $previewToken = hash('sha256', 'source|'.$sha256.'|'.microtime(true));
        $createdAt = now();
        $expiresAt = $createdAt->copy()->addMinutes(self::PREVIEW_TTL_MINUTES);

        session()->put('import_previews.'.$previewToken, [
            'import_type' => 'source',
            'preview' => $preview,
            'sha256' => $sha256,
            'original_filename' => $file->getClientOriginalName(),
            'created_at' => $createdAt->toIso8601String(),
            'expires_at' => $expiresAt->toIso8601String(),
        ]);

        return view('imports.preview', [
            'title' => 'Source File CSV Preview',
            'postRoute' => 'imports.source-files.preview.store',
            'commitRoute' => 'imports.source-files.preview.commit',
            'importType' => 'source',
            'preview' => $preview,
            'previewToken' => $previewToken,
            'safetyNote' => 'Preview-only for synthetic/dev CSV. No file is stored and no staging rows are inserted.',
        ]);
    }

    public function commitPreview(
        CommitPreviewImportRequest $request,
        StagingImportService $stagingImportService,
        AuditLogger $auditLogger,
    ): RedirectResponse {
        $token = (string) $request->input('preview_token');
        $entry = session('import_previews.'.$token);

        if (! is_array($entry) || ($entry['import_type'] ?? null) !== 'source') {
            return back()->withErrors(['preview_token' => 'Preview token is missing or expired.']);
        }

        $expirationFailure = $this->previewExpirationFailureReason($entry);
        if ($expirationFailure !== null) {
            return back()->withErrors(['preview_token' => $expirationFailure]);
        }

        if (($entry['preview']['errors'] ?? []) !== []) {
            return back()->withErrors(['preview_token' => 'Preview with errors cannot be committed.']);
        }

        try {
            $result = DB::transaction(function () use ($entry, $request, $stagingImportService, $auditLogger): array {
                $result = $stagingImportService->persistSourcePreview($entry['preview'], [
                    'job_name' => 'Committed source preview',
                    'original_filename' => $entry['original_filename'] ?? 'synthetic-preview.csv',
                    'sha256' => $entry['sha256'],
                ]);

                $auditLogger->log('import_preview_committed', 'source_import_job', $result['source_import_job_id'], [
                    'ip_address' => $request->ip(),
                    'user_agent' => $request->userAgent(),
                    'after_payload' => [
                        'import_type' => 'source',
                        'sha256' => $result['sha256'],
                        'rows_inserted' => $result['rows_inserted'],
                        'file_stored' => false,
                    ],
                ]);

                return $result;
            });
        } catch (LogicException $exception) {
            return back()->withErrors(['preview_token' => $exception->getMessage()]);
        }

        session()->forget('import_previews.'.$token);

        return redirect()
            ->route('imports.source-files.show', ['job' => $result['source_import_job_id']])
            ->with('status', 'Preview committed to staging.');
    }

    private function previewExpirationFailureReason(array $entry): ?string
    {
        if (! is_string($entry['created_at'] ?? null) || ! is_string($entry['expires_at'] ?? null)) {
            return 'PREVIEW_EXPIRATION_INVALID';
        }

        try {
            $createdAt = CarbonImmutable::parse($entry['created_at']);
            $expiresAt = CarbonImmutable::parse($entry['expires_at']);
        } catch (\Throwable) {
            return 'PREVIEW_EXPIRATION_INVALID';
        }

        if (! $expiresAt->equalTo($createdAt->addMinutes(self::PREVIEW_TTL_MINUTES))) {
            return 'PREVIEW_EXPIRATION_INVALID';
        }

        $now = now();

        if ($now->lessThan($createdAt)) {
            return 'PREVIEW_EXPIRATION_INVALID';
        }

        if ($now->greaterThanOrEqualTo($expiresAt)) {
            return 'PREVIEW_EXPIRED';
        }

        return null;
    }

    private function cleanupTempImports(): void
    {
        if (Storage::disk('local')->exists('imports/temp')) {
            Storage::disk('local')->deleteDirectory('imports/temp');
        }
    }
}