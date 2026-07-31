<?php

namespace App\Services\Export;

use App\Models\ExportJob;
use App\Services\Audit\AuditLogger;
use DomainException;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;
use LogicException;
use RuntimeException;
use Throwable;

final class ExportService
{
    public const BLOCKED_STATUS = 'blocked_not_implemented';

    public const DISABLED_WARNING = 'Export file generation is not enabled yet.';

    public const RESULT_CATEGORIES = [
        'has_history',
        'no_history',
        'invalid_identifier',
        'missing_identifier',
        'needs_review',
    ];

    public function __construct(
        private ?ExportDisclosurePolicy $disclosurePolicy = null,
        private ?ExportCsvWriter $csvWriter = null,
        private ?AuditLogger $auditLogger = null,
    ) {
        $this->disclosurePolicy ??= new ExportDisclosurePolicy;
        $this->csvWriter ??= new ExportCsvWriter;
        $this->auditLogger ??= new AuditLogger;
    }

    public function queueExport(string $exportType, array $filters): array
    {
        return $this->createBlockedExportJob($exportType, $filters);
    }

    /**
     * W7 contract only: record the blocked export intent without creating files.
     *
     * Future export execution must read from stored target_group_results and
     * target_group_result_sources, preserve filters/provenance, and write audit
     * evidence before exposing any stored_path for download.
     */
    public function createBlockedExportJob(string $exportType, array $filters): array
    {
        $id = DB::table('export_jobs')->insertGetId([
            'export_type' => $exportType,
            'status' => self::BLOCKED_STATUS,
            'filters' => json_encode($filters),
            'stored_path' => null,
            'row_count' => null,
            'error_message' => 'Export generation is not enabled yet.',
            'started_at' => null,
            'finished_at' => null,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return [
            'id' => $id,
            'status' => self::BLOCKED_STATUS,
            'stored_path' => null,
            'file_created' => false,
        ];
    }

    public function assertExportEligible(array $filters): array
    {
        $preview = $this->buildExportPreview($filters);

        if (! $preview['eligible']) {
            throw new InvalidArgumentException($preview['eligibility_reason']);
        }

        return $preview;
    }

    public function buildExportPreview(array $filters): array
    {
        $context = $this->resolveResultContext($filters);
        $categoryFilters = $this->normalizeCategoryFilters($filters['categories'] ?? []);
        $baseQuery = $this->baseResultQuery($context);
        $unfilteredResultCount = (clone $baseQuery)->distinct('target_group_results.id')->count('target_group_results.id');
        $invalidCategoryCount = (clone $baseQuery)
            ->whereNotIn('target_group_results.result_category', self::RESULT_CATEGORIES)
            ->distinct('target_group_results.id')
            ->count('target_group_results.id');

        $filteredQuery = $this->baseResultQuery($context);
        if ($categoryFilters !== []) {
            $filteredQuery->whereIn('target_group_results.result_category', $categoryFilters);
        }

        $totalResultRows = (clone $filteredQuery)->distinct('target_group_results.id')->count('target_group_results.id');
        $categoryCounts = array_fill_keys(self::RESULT_CATEGORIES, 0);
        $rawCounts = (clone $filteredQuery)
            ->select('target_group_results.result_category', DB::raw('count(distinct target_group_results.id) as aggregate_count'))
            ->whereIn('target_group_results.result_category', self::RESULT_CATEGORIES)
            ->groupBy('target_group_results.result_category')
            ->pluck('aggregate_count', 'target_group_results.result_category');

        foreach ($rawCounts as $category => $count) {
            $categoryCounts[$category] = (int) $count;
        }

        $resultIds = (clone $filteredQuery)
            ->select('target_group_results.id')
            ->distinct()
            ->pluck('target_group_results.id');

        $sourceRecordCount = 0;
        $resultsWithProvenanceCount = 0;
        if ($resultIds->isNotEmpty()) {
            $sourceRecordCount = DB::table('target_group_result_sources')
                ->whereIn('target_group_result_id', $resultIds)
                ->count();
            $resultsWithProvenanceCount = DB::table('target_group_result_sources')
                ->whereIn('target_group_result_id', $resultIds)
                ->distinct('target_group_result_id')
                ->count('target_group_result_id');
        }

        $eligible = $unfilteredResultCount > 0 && $totalResultRows > 0 && $invalidCategoryCount === 0;

        return [
            'target_group_job_id' => $context['target_group_job_id'],
            'result_generation_job_id' => $context['result_generation_job_id'],
            'total_stored_result_rows' => $totalResultRows,
            'category_counts' => $categoryCounts,
            'result_source_provenance_count' => $sourceRecordCount,
            'results_with_provenance_count' => $resultsWithProvenanceCount,
            'results_without_provenance_count' => max(0, $totalResultRows - $resultsWithProvenanceCount),
            'selected_filter_summary' => [
                'target_group_job_id' => $context['target_group_job_id'],
                'result_generation_job_id' => $context['result_generation_job_id'],
                'categories' => $categoryFilters,
                'source' => 'persisted_target_group_results_only',
            ],
            'eligible' => $eligible,
            'eligibility_status' => $eligible ? 'eligible' : 'not_eligible',
            'eligibility_reason' => $this->eligibilityReason($unfilteredResultCount, $totalResultRows, $invalidCategoryCount),
            'warning' => self::DISABLED_WARNING,
        ];
    }

    public function generateFileFromStoredResults(string $exportType, array $filters): never
    {
        throw new LogicException('Export generation is not enabled yet.');
    }

    public function createAndGenerateCsvExport(array $filters): ExportJob
    {
        $this->validateGenerationColumns($filters['columns'] ?? $this->disclosurePolicy->allowedColumns());
        $safeFilters = $this->prepareGenerationFilters($filters);
        $preview = $this->assertExportEligible($safeFilters);
        $resultGenerationJob = $this->resolvePersistedGenerationContext($safeFilters, $preview);

        $safeFilters = [
            'target_group_job_id' => (int) $resultGenerationJob->target_group_job_id,
            'result_generation_job_id' => (int) $resultGenerationJob->id,
            'categories' => $safeFilters['categories'],
            'policy_version' => $this->disclosurePolicy->version(),
            'source' => 'persisted_target_group_results_only',
        ];

        $job = ExportJob::create([
            'export_type' => 'deidentified_csv',
            'status' => 'pending',
            'requested_by_user_id' => $filters['requested_by_user_id'] ?? null,
            'filters' => $safeFilters,
        ]);

        return $this->generateCsvForExportJob($job->id);
    }

    public function generateCsvForExportJob(int $exportJobId): ExportJob
    {
        $job = ExportJob::findOrFail($exportJobId);

        if ($job->status === 'completed') {
            return $this->verifyCompletedArtifact($job);
        }

        if ($job->status !== 'pending') {
            throw new RuntimeException('export_job_not_pending');
        }

        $filters = $this->prepareGenerationFilters($job->filters);
        $this->disclosurePolicy->validateColumnSelection($this->disclosurePolicy->allowedColumns());
        $preview = $this->assertExportEligible($filters);
        $resultGenerationJob = $this->resolvePersistedGenerationContext($filters, $preview);
        $rows = $this->buildStoredResultExportRows($filters, $resultGenerationJob);

        $filename = 'export-'.$job->id.'-'.bin2hex(random_bytes(8)).'.csv';
        $storedPath = 'exports/'.$filename;
        $finalPath = storage_path('app/'.$storedPath);
        $finalExistedBeforeAttempt = is_file($finalPath);

        $job->update([
            'status' => 'generating',
            'started_at' => now(),
            'finished_at' => null,
            'error_message' => null,
        ]);

        try {
            $metadata = $this->csvWriter->write(
                $finalPath,
                $this->disclosurePolicy->allowedColumns(),
                $rows,
            );

            if ($metadata['row_count'] !== count($rows) || ! is_file($finalPath)) {
                throw new RuntimeException('export_artifact_verification_failed');
            }

            $measuredBytes = filesize($finalPath);
            $measuredSha256 = hash_file('sha256', $finalPath);
            if ($measuredBytes !== $metadata['byte_count'] || $measuredSha256 !== $metadata['sha256']) {
                throw new RuntimeException('export_artifact_verification_failed');
            }

            $job->update([
                'status' => 'completed',
                'stored_path' => $storedPath,
                'generated_filename' => $filename,
                'mime_type' => ExportCsvWriter::MIME_TYPE,
                'row_count' => $metadata['row_count'],
                'byte_count' => $metadata['byte_count'],
                'sha256' => strtolower($metadata['sha256']),
                'error_message' => null,
                'finished_at' => now(),
            ]);

            $this->auditLogger->log('export_csv_generated', 'export_job', $job->id, [
                'actor_user_id' => $job->requested_by_user_id,
                'after_payload' => [
                    'export_job_id' => $job->id,
                    'target_group_job_id' => (int) $resultGenerationJob->target_group_job_id,
                    'result_generation_job_id' => (int) $resultGenerationJob->id,
                    'policy_version' => $this->disclosurePolicy->version(),
                    'categories' => $filters['categories'],
                    'row_count' => $metadata['row_count'],
                    'byte_count' => $metadata['byte_count'],
                    'sha256' => strtolower($metadata['sha256']),
                    'mime_type' => ExportCsvWriter::MIME_TYPE,
                    'file_stored' => true,
                    'storage_visibility' => 'private',
                ],
            ]);

            return $job->fresh();
        } catch (Throwable $exception) {
            if (! $finalExistedBeforeAttempt && is_file($finalPath)) {
                @unlink($finalPath);
            }

            $job->update([
                'status' => 'failed',
                'stored_path' => null,
                'generated_filename' => null,
                'mime_type' => null,
                'row_count' => null,
                'byte_count' => null,
                'sha256' => null,
                'error_message' => 'csv_generation_failed',
                'finished_at' => now(),
            ]);

            throw new RuntimeException('csv_generation_failed', previous: $exception);
        }
    }

    public function buildStoredResultExportRows(array $filters, object $resultGenerationJob): array
    {
        $query = DB::table('target_group_results')
            ->where('target_group_job_id', (int) $resultGenerationJob->target_group_job_id)
            ->where('result_generation_job_id', (int) $resultGenerationJob->id)
            ->select([
                'target_group_results.id',
                'target_group_results.result_category',
                'target_group_results.review_status',
                'target_group_results.latest_history_date',
                'target_group_results.latest_history_source',
            ])
            ->selectSub(function ($sources): void {
                $sources->from('target_group_result_sources')
                    ->selectRaw('count(*)')
                    ->whereColumn('target_group_result_sources.target_group_result_id', 'target_group_results.id');
            }, 'evidence_source_count')
            ->orderBy('target_group_results.id');

        if ($filters['categories'] !== []) {
            $query->whereIn('target_group_results.result_category', $filters['categories']);
        }

        $selectedServiceKeys = json_decode($resultGenerationJob->selected_service_keys, true, flags: JSON_THROW_ON_ERROR);
        if (! is_array($selectedServiceKeys)) {
            throw new RuntimeException('persisted_service_context_invalid');
        }

        $selectedServiceKeys = array_values(array_unique(array_map('strval', $selectedServiceKeys)));
        sort($selectedServiceKeys, SORT_STRING);
        $serializedServiceKeys = json_encode($selectedServiceKeys, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);

        return $query->get()->values()->map(static function (object $result, int $index) use ($resultGenerationJob, $serializedServiceKeys): array {
            $sourceCount = (int) $result->evidence_source_count;

            return [
                $index + 1,
                $result->result_category,
                $result->review_status,
                $result->latest_history_date,
                $result->latest_history_source,
                $sourceCount,
                $sourceCount > 0 ? 'true' : 'false',
                $serializedServiceKeys,
                (int) $resultGenerationJob->target_group_job_id,
                (int) $resultGenerationJob->id,
            ];
        })->all();
    }

    private function prepareGenerationFilters(array $filters): array
    {
        $categories = $filters['categories'] ?? [];
        if ($categories === null || $categories === '') {
            $categories = [];
        }
        if (is_string($categories)) {
            $categories = [$categories];
        }
        if (! is_array($categories)) {
            throw new InvalidArgumentException('invalid_result_category_filter');
        }

        $normalized = array_values(array_unique(array_map(
            static fn (mixed $category): string => strtolower(trim((string) $category)),
            $categories,
        )));
        foreach ($normalized as $category) {
            if (! in_array($category, self::RESULT_CATEGORIES, true)) {
                throw new InvalidArgumentException('invalid_result_category_filter');
            }
        }

        return [
            'target_group_job_id' => isset($filters['target_group_job_id']) ? (int) $filters['target_group_job_id'] : null,
            'result_generation_job_id' => isset($filters['result_generation_job_id']) ? (int) $filters['result_generation_job_id'] : null,
            'categories' => $normalized,
        ];
    }

    private function validateGenerationColumns(array $columns): void
    {
        $validated = $this->disclosurePolicy->validateColumnSelection($columns);
        if ($validated !== $this->disclosurePolicy->allowedColumns()) {
            throw new DomainException('CSV export requires the complete deidentified column contract.');
        }
    }

    private function resolvePersistedGenerationContext(array $filters, array $preview): object
    {
        $resultGenerationJobId = $filters['result_generation_job_id'];

        if ($resultGenerationJobId === null) {
            $query = DB::table('target_group_results')
                ->where('target_group_job_id', $preview['target_group_job_id']);
            if ($filters['categories'] !== []) {
                $query->whereIn('result_category', $filters['categories']);
            }

            $generationIds = $query->distinct()->pluck('result_generation_job_id');
            if ($generationIds->count() !== 1) {
                throw new InvalidArgumentException('ambiguous_result_generation_context');
            }

            $resultGenerationJobId = (int) $generationIds->first();
        }

        $job = DB::table('result_generation_jobs')->where('id', $resultGenerationJobId)->first();
        if ($job === null || (int) $job->target_group_job_id !== (int) $preview['target_group_job_id']) {
            throw new InvalidArgumentException('result_generation_job_target_group_mismatch');
        }

        return $job;
    }

    private function verifyCompletedArtifact(ExportJob $job): ExportJob
    {
        $filename = $job->generated_filename;
        $storedPath = $job->stored_path;
        $validLocation = is_string($filename)
            && basename($filename) === $filename
            && is_string($storedPath)
            && $storedPath === 'exports/'.$filename;
        $path = $validLocation ? storage_path('app/'.$storedPath) : null;

        if (! $validLocation
            || ! is_file($path)
            || filesize($path) !== $job->byte_count
            || hash_file('sha256', $path) !== $job->sha256) {
            $job->update([
                'status' => 'failed',
                'error_message' => 'completed_artifact_verification_failed',
                'finished_at' => now(),
            ]);

            throw new RuntimeException('completed_artifact_verification_failed');
        }

        return $job->fresh();
    }

    private function resolveResultContext(array $filters): array
    {
        $targetGroupJobId = $filters['target_group_job_id'] ?? null;
        $resultGenerationJobId = $filters['result_generation_job_id'] ?? null;

        if ($targetGroupJobId !== null) {
            $targetGroupJobId = (int) $targetGroupJobId;
            $targetGroupExists = DB::table('target_group_jobs')->where('id', $targetGroupJobId)->exists();
            if (! $targetGroupExists) {
                throw new InvalidArgumentException('target_group_job_not_found');
            }
        }

        if ($resultGenerationJobId !== null) {
            $resultGenerationJobId = (int) $resultGenerationJobId;
            $resultGenerationJob = DB::table('result_generation_jobs')->where('id', $resultGenerationJobId)->first();
            if ($resultGenerationJob === null) {
                throw new InvalidArgumentException('result_generation_job_not_found');
            }

            if ($targetGroupJobId !== null && (int) $resultGenerationJob->target_group_job_id !== $targetGroupJobId) {
                throw new InvalidArgumentException('result_generation_job_target_group_mismatch');
            }

            $targetGroupJobId = (int) $resultGenerationJob->target_group_job_id;
        }

        if ($targetGroupJobId === null) {
            throw new InvalidArgumentException('target_group_job_or_result_generation_job_required');
        }

        return [
            'target_group_job_id' => $targetGroupJobId,
            'result_generation_job_id' => $resultGenerationJobId,
        ];
    }

    private function baseResultQuery(array $context)
    {
        $query = DB::table('target_group_results')
            ->where('target_group_job_id', $context['target_group_job_id']);

        if ($context['result_generation_job_id'] !== null) {
            $query->where('result_generation_job_id', $context['result_generation_job_id']);
        }

        return $query;
    }

    private function normalizeCategoryFilters(array|string|null $categories): array
    {
        if ($categories === null || $categories === '') {
            return [];
        }

        if (is_string($categories)) {
            $categories = [$categories];
        }

        return array_values(array_intersect(self::RESULT_CATEGORIES, array_unique($categories)));
    }

    private function eligibilityReason(int $unfilteredResultCount, int $filteredResultCount, int $invalidCategoryCount): string
    {
        if ($unfilteredResultCount === 0) {
            return 'no_stored_results';
        }

        if ($invalidCategoryCount > 0) {
            return 'invalid_persisted_result_category';
        }

        if ($filteredResultCount === 0) {
            return 'filters_match_no_stored_results';
        }

        return 'eligible';
    }
}
