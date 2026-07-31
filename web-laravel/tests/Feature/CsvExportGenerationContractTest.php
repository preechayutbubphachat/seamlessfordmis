<?php

namespace Tests\Feature;

use App\Services\Audit\AuditLogger;
use App\Services\Export\ExportCsvWriter;
use App\Services\Export\ExportDisclosurePolicy;
use App\Services\Export\ExportService;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;
use RuntimeException;
use Tests\TestCase;

final class CsvExportGenerationContractTest extends TestCase
{
    use RefreshDatabase;

    private array $preExistingExportFiles = [];

    protected function setUp(): void
    {
        parent::setUp();
        $this->preExistingExportFiles = $this->exportFiles();
    }

    protected function tearDown(): void
    {
        foreach (array_diff($this->exportFiles(), $this->preExistingExportFiles) as $file) {
            @unlink($file);
        }
        $directory = storage_path('app/exports');
        if (is_dir($directory) && $this->exportFiles() === []) {
            @rmdir($directory);
        }
        parent::tearDown();
    }

    public function test_no_results_and_staging_only_data_are_ineligible(): void
    {
        $targetJobId = $this->createTargetGroupJob();

        try {
            (new ExportService)->createAndGenerateCsvExport(['target_group_job_id' => $targetJobId]);
            $this->fail('A job without stored results must be rejected.');
        } catch (InvalidArgumentException $exception) {
            $this->assertSame('no_stored_results', $exception->getMessage());
        }

        $this->createStagingRow($targetJobId);

        try {
            (new ExportService)->createAndGenerateCsvExport(['target_group_job_id' => $targetJobId]);
            $this->fail('Staging rows must not make an export eligible.');
        } catch (InvalidArgumentException $exception) {
            $this->assertSame('no_stored_results', $exception->getMessage());
        }

        $this->assertDatabaseCount('export_jobs', 0);
        $this->assertSame([], array_diff($this->exportFiles(), $this->preExistingExportFiles));
    }

    public function test_generation_exports_each_persisted_result_once_with_categories_and_provenance_counts(): void
    {
        $targetJobId = $this->createTargetGroupJob();
        $resultJobId = $this->createResultGenerationJob($targetJobId, ['technical-z', 'technical-a']);
        $categories = ExportService::RESULT_CATEGORIES;
        $resultIds = [];
        foreach ($categories as $category) {
            $resultIds[] = $this->createResult($targetJobId, $resultJobId, $category);
        }
        $this->createSource($resultIds[0]);
        $this->createSource($resultIds[0]);
        $this->createSource($resultIds[4]);
        $resultCountBefore = DB::table('target_group_results')->count();
        $sourceCountBefore = DB::table('target_group_result_sources')->count();

        $job = (new ExportService)->createAndGenerateCsvExport([
            'result_generation_job_id' => $resultJobId,
        ]);
        $path = storage_path('app/'.$job->stored_path);
        $rows = $this->readCsv($path);

        $this->assertSame('completed', $job->status);
        $this->assertSame((new ExportDisclosurePolicy)->allowedColumns(), $rows[0]);
        $this->assertCount(6, $rows);
        $this->assertSame($categories, array_column(array_slice($rows, 1), 1));
        $this->assertSame(['1', '2', '3', '4', '5'], array_column(array_slice($rows, 1), 0));
        $this->assertSame('2', $rows[1][5]);
        $this->assertSame('true', $rows[1][6]);
        $this->assertSame('0', $rows[2][5]);
        $this->assertSame('false', $rows[2][6]);
        $this->assertSame('["technical-a","technical-z"]', $rows[1][7]);
        $this->assertSame(5, $job->row_count);
        $this->assertSame(filesize($path), $job->byte_count);
        $this->assertSame(hash_file('sha256', $path), $job->sha256);
        $this->assertSame('text/csv', $job->mime_type);
        $this->assertSame($job->generated_filename, basename($job->stored_path));
        $this->assertSame('exports/'.$job->generated_filename, $job->stored_path);
        $this->assertStringNotContainsString('raw_payload', file_get_contents($path));
        $this->assertStringNotContainsString('review_reason', file_get_contents($path));
        $this->assertStringNotContainsString('TECHNICAL_PROVENANCE_MUST_NOT_EXPORT', file_get_contents($path));
        $this->assertStringNotContainsString('TECHNICAL_SOURCE_CONTENT_MUST_NOT_EXPORT', file_get_contents($path));
        $this->assertSame($resultCountBefore, DB::table('target_group_results')->count());
        $this->assertSame($sourceCountBefore, DB::table('target_group_result_sources')->count());
    }

    public function test_unrelated_results_and_staging_changes_do_not_affect_filtered_output(): void
    {
        $firstTargetId = $this->createTargetGroupJob('technical-first');
        $firstGenerationId = $this->createResultGenerationJob($firstTargetId, ['technical-service']);
        $this->createResult($firstTargetId, $firstGenerationId, 'invalid_identifier');
        $this->createStagingRow($firstTargetId);

        $secondTargetId = $this->createTargetGroupJob('technical-second');
        $secondGenerationId = $this->createResultGenerationJob($secondTargetId, ['unrelated-service']);
        $this->createResult($secondTargetId, $secondGenerationId, 'has_history');

        $job = (new ExportService)->createAndGenerateCsvExport([
            'result_generation_job_id' => $firstGenerationId,
            'categories' => ['invalid_identifier'],
        ]);
        $rows = $this->readCsv(storage_path('app/'.$job->stored_path));

        $this->assertCount(2, $rows);
        $this->assertSame('invalid_identifier', $rows[1][1]);
        $this->assertSame((string) $firstTargetId, $rows[1][8]);
        $this->assertSame((string) $firstGenerationId, $rows[1][9]);
        $this->assertNotSame((string) $secondGenerationId, $rows[1][9]);
    }

    public function test_invalid_category_and_prohibited_or_partial_columns_fail_before_job_creation(): void
    {
        $targetJobId = $this->createTargetGroupJob();
        $resultJobId = $this->createResultGenerationJob($targetJobId, ['technical-service']);
        $this->createResult($targetJobId, $resultJobId, 'has_history');
        $service = new ExportService;

        foreach ([
            ['result_generation_job_id' => $resultJobId, 'categories' => ['unknown_category']],
            ['result_generation_job_id' => $resultJobId, 'columns' => ['result_category', 'raw_cid']],
            ['result_generation_job_id' => $resultJobId, 'columns' => ['result_category']],
        ] as $filters) {
            try {
                $service->createAndGenerateCsvExport($filters);
                $this->fail('Invalid generation contract must fail closed.');
            } catch (InvalidArgumentException|DomainException) {
                $this->addToAssertionCount(1);
            }
        }

        $this->assertDatabaseCount('export_jobs', 0);
    }

    public function test_completed_retry_reuses_verified_artifact_without_rewrite_or_duplicate_audit(): void
    {
        $targetJobId = $this->createTargetGroupJob();
        $resultJobId = $this->createResultGenerationJob($targetJobId, ['technical-service']);
        $this->createResult($targetJobId, $resultJobId, 'no_history');
        $service = new ExportService;
        $job = $service->createAndGenerateCsvExport(['result_generation_job_id' => $resultJobId]);
        $path = storage_path('app/'.$job->stored_path);
        $mtime = filemtime($path);
        $files = $this->exportFiles();

        $retried = $service->generateCsvForExportJob($job->id);

        $this->assertSame($job->sha256, $retried->sha256);
        $this->assertSame($mtime, filemtime($path));
        $this->assertSame($files, $this->exportFiles());
        $this->assertDatabaseCount('export_jobs', 1);
        $this->assertSame(1, DB::table('audit_logs')->where('action', 'export_csv_generated')->count());
    }

    public function test_corrupt_completed_artifact_is_rejected_without_overwrite(): void
    {
        $targetJobId = $this->createTargetGroupJob();
        $resultJobId = $this->createResultGenerationJob($targetJobId, ['technical-service']);
        $this->createResult($targetJobId, $resultJobId, 'needs_review');
        $service = new ExportService;
        $job = $service->createAndGenerateCsvExport(['result_generation_job_id' => $resultJobId]);
        $path = storage_path('app/'.$job->stored_path);
        file_put_contents($path, 'corrupt-technical-artifact');

        try {
            $service->generateCsvForExportJob($job->id);
            $this->fail('A corrupted completed artifact must not be accepted.');
        } catch (RuntimeException $exception) {
            $this->assertSame('completed_artifact_verification_failed', $exception->getMessage());
        }

        $this->assertSame('corrupt-technical-artifact', file_get_contents($path));
        $this->assertDatabaseHas('export_jobs', [
            'id' => $job->id,
            'status' => 'failed',
            'error_message' => 'completed_artifact_verification_failed',
        ]);
        $this->assertSame(1, DB::table('audit_logs')->where('action', 'export_csv_generated')->count());
    }

    public function test_write_failure_marks_job_failed_cleans_metadata_and_writes_no_success_audit(): void
    {
        $targetJobId = $this->createTargetGroupJob();
        $resultJobId = $this->createResultGenerationJob($targetJobId, ['technical-service']);
        $this->createResult($targetJobId, $resultJobId, 'missing_identifier');
        $failingWriter = new class extends ExportCsvWriter
        {
            public function write(string $finalPath, array $header, iterable $rows): array
            {
                if (! is_dir(dirname($finalPath))) {
                    mkdir(dirname($finalPath), 0700, true);
                }
                file_put_contents($finalPath, 'incomplete-technical-artifact');
                throw new RuntimeException('simulated_write_failure');
            }
        };
        $service = new ExportService(new ExportDisclosurePolicy, $failingWriter, new AuditLogger);

        try {
            $service->createAndGenerateCsvExport(['result_generation_job_id' => $resultJobId]);
            $this->fail('Simulated write failure must propagate a controlled failure.');
        } catch (RuntimeException $exception) {
            $this->assertSame('csv_generation_failed', $exception->getMessage());
        }

        $job = DB::table('export_jobs')->first();
        $this->assertSame('failed', $job->status);
        $this->assertSame('csv_generation_failed', $job->error_message);
        $this->assertNull($job->stored_path);
        $this->assertNull($job->generated_filename);
        $this->assertNull($job->byte_count);
        $this->assertNull($job->sha256);
        $this->assertDatabaseCount('audit_logs', 0);
        $this->assertSame([], array_diff($this->exportFiles(), $this->preExistingExportFiles));
    }

    public function test_success_audit_contains_operational_metadata_only(): void
    {
        $targetJobId = $this->createTargetGroupJob();
        $resultJobId = $this->createResultGenerationJob($targetJobId, ['technical-service']);
        $this->createResult($targetJobId, $resultJobId, 'has_history');
        $job = (new ExportService)->createAndGenerateCsvExport([
            'result_generation_job_id' => $resultJobId,
        ]);
        $audit = DB::table('audit_logs')->where('action', 'export_csv_generated')->first();
        $metadata = json_decode($audit->after_payload, true, flags: JSON_THROW_ON_ERROR);

        $this->assertSame('export_job', $audit->entity_type);
        $this->assertSame($job->id, $audit->entity_id);
        $this->assertSame($job->sha256, $metadata['sha256']);
        $this->assertSame('deidentified_internal_v1', $metadata['policy_version']);
        $this->assertTrue($metadata['file_stored']);
        $this->assertSame('private', $metadata['storage_visibility']);
        $encoded = json_encode($metadata);
        foreach (['raw_cid', 'display_name', 'raw_payload', 'csv_content', storage_path()] as $prohibited) {
            $this->assertStringNotContainsString($prohibited, $encoded);
        }
    }

    private function createTargetGroupJob(string $label = 'technical-target-group'): int
    {
        return DB::table('target_group_jobs')->insertGetId([
            'group_name' => $label,
            'status' => 'technical_ready',
            'total_files' => 0,
            'total_rows' => 0,
            'valid_rows' => 0,
            'invalid_rows' => 0,
            'review_rows' => 0,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function createResultGenerationJob(int $targetJobId, array $serviceKeys): int
    {
        return DB::table('result_generation_jobs')->insertGetId([
            'target_group_job_id' => $targetJobId,
            'status' => 'completed',
            'selected_service_keys' => json_encode($serviceKeys),
            'normalization_version' => 1,
            'total_persons' => 0,
            'completed_persons' => 0,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function createResult(int $targetJobId, int $resultJobId, string $category): int
    {
        return DB::table('target_group_results')->insertGetId([
            'target_group_job_id' => $targetJobId,
            'result_generation_job_id' => $resultJobId,
            'person_key' => 'technical-key-'.uniqid(),
            'result_category' => $category,
            'has_screening_db_history' => $category === 'has_history',
            'has_target_group_file_history' => false,
            'has_any_history' => $category === 'has_history',
            'latest_history_date' => $category === 'has_history' ? '2020-01-02' : null,
            'latest_history_source' => $category === 'has_history' ? 'technical,"source"' : null,
            'selected_service_keys' => json_encode(['ignored-result-copy']),
            'evidence_summary' => json_encode(['technical' => true]),
            'review_status' => $category === 'needs_review' ? "technical\nreview" : 'technical_clear',
            'review_reason' => 'TECHNICAL_REVIEW_REASON_MUST_NOT_EXPORT',
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function createSource(int $resultId): void
    {
        DB::table('target_group_result_sources')->insert([
            'target_group_result_id' => $resultId,
            'source_type' => 'technical_source',
            'source_payload' => json_encode(['TECHNICAL_SOURCE_CONTENT_MUST_NOT_EXPORT']),
            'provenance' => json_encode(['TECHNICAL_PROVENANCE_MUST_NOT_EXPORT']),
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function createStagingRow(int $targetJobId): void
    {
        $fileId = DB::table('target_group_files')->insertGetId([
            'target_group_job_id' => $targetJobId,
            'original_filename' => 'technical-no-file',
            'stored_path' => '__technical_no_file__',
            'mime_type' => 'text/plain',
            'size_bytes' => 0,
            'sha256' => hash('sha256', 'technical-staging-'.$targetJobId),
            'row_count' => 1,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        DB::table('target_group_rows')->insert([
            'target_group_job_id' => $targetJobId,
            'target_group_file_id' => $fileId,
            'row_number' => 1,
            'raw_payload' => json_encode(['technical_staging' => true]),
            'cid_status' => 'missing_identifier',
            'validation_status' => 'missing_identifier',
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function readCsv(string $path): array
    {
        $handle = fopen($path, 'rb');
        $this->assertSame(ExportCsvWriter::UTF8_BOM, fread($handle, 3));
        $rows = [];
        while (($row = fgetcsv($handle, escape: '')) !== false) {
            $rows[] = $row;
        }
        fclose($handle);

        return $rows;
    }

    private function exportFiles(): array
    {
        $files = glob(storage_path('app/exports/*')) ?: [];
        $files = array_values(array_filter($files, 'is_file'));
        sort($files);

        return $files;
    }
}
