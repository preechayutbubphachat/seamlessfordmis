<?php

namespace Tests\Unit;

use App\Services\Export\ExportService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class ExportServicePreviewTest extends TestCase
{
    use RefreshDatabase;

    public function test_job_with_no_stored_results_is_not_eligible(): void
    {
        $jobId = $this->createTargetGroupJob();

        $preview = (new ExportService())->buildExportPreview([
            'target_group_job_id' => $jobId,
        ]);

        $this->assertFalse($preview['eligible']);
        $this->assertSame('no_stored_results', $preview['eligibility_reason']);
        $this->assertSame(0, $preview['total_stored_result_rows']);
    }

    public function test_staging_rows_alone_do_not_make_job_eligible(): void
    {
        $jobId = $this->createTargetGroupJob();
        $fileId = DB::table('target_group_files')->insertGetId([
            'target_group_job_id' => $jobId,
            'original_filename' => 'synthetic-preview-source',
            'stored_path' => '__synthetic_no_file_stored__',
            'mime_type' => 'text/plain',
            'size_bytes' => 0,
            'sha256' => hash('sha256', 'staging-only-'.$jobId),
            'row_count' => 1,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        DB::table('target_group_rows')->insert([
            'target_group_job_id' => $jobId,
            'target_group_file_id' => $fileId,
            'row_number' => 1,
            'raw_payload' => json_encode(['synthetic_marker' => 'STAGING_ONLY']),
            'cid_status' => 'missing_identifier',
            'validation_status' => 'missing_identifier',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $preview = (new ExportService())->buildExportPreview([
            'target_group_job_id' => $jobId,
        ]);

        $this->assertFalse($preview['eligible']);
        $this->assertSame('no_stored_results', $preview['eligibility_reason']);
        $this->assertSame(0, $preview['total_stored_result_rows']);
    }

    public function test_aggregate_counts_and_provenance_are_calculated_from_stored_results(): void
    {
        $jobId = $this->createTargetGroupJob();
        $resultJobId = $this->createResultGenerationJob($jobId);
        $firstResultId = $this->createResult($jobId, $resultJobId, 'has_history');
        $this->createResult($jobId, $resultJobId, 'no_history');
        $this->createResult($jobId, $resultJobId, 'invalid_identifier');
        $this->createSource($firstResultId);
        $this->createSource($firstResultId);

        $preview = (new ExportService())->buildExportPreview([
            'result_generation_job_id' => $resultJobId,
        ]);

        $this->assertTrue($preview['eligible']);
        $this->assertSame(3, $preview['total_stored_result_rows']);
        $this->assertSame(1, $preview['category_counts']['has_history']);
        $this->assertSame(1, $preview['category_counts']['no_history']);
        $this->assertSame(1, $preview['category_counts']['invalid_identifier']);
        $this->assertSame(0, $preview['category_counts']['missing_identifier']);
        $this->assertSame(0, $preview['category_counts']['needs_review']);
        $this->assertSame(2, $preview['result_source_provenance_count']);
        $this->assertSame(1, $preview['results_with_provenance_count']);
        $this->assertSame(2, $preview['results_without_provenance_count']);
    }

    public function test_results_from_another_job_are_not_included(): void
    {
        $firstJobId = $this->createTargetGroupJob('synthetic-one');
        $firstResultJobId = $this->createResultGenerationJob($firstJobId);
        $secondJobId = $this->createTargetGroupJob('synthetic-two');
        $secondResultJobId = $this->createResultGenerationJob($secondJobId);
        $this->createResult($firstJobId, $firstResultJobId, 'has_history');
        $this->createResult($secondJobId, $secondResultJobId, 'missing_identifier');

        $preview = (new ExportService())->buildExportPreview([
            'target_group_job_id' => $firstJobId,
        ]);

        $this->assertSame(1, $preview['total_stored_result_rows']);
        $this->assertSame(1, $preview['category_counts']['has_history']);
        $this->assertSame(0, $preview['category_counts']['missing_identifier']);
    }

    public function test_category_filter_is_reflected_without_changing_zero_count_categories(): void
    {
        $jobId = $this->createTargetGroupJob();
        $resultJobId = $this->createResultGenerationJob($jobId);
        $this->createResult($jobId, $resultJobId, 'has_history');
        $this->createResult($jobId, $resultJobId, 'no_history');

        $preview = (new ExportService())->buildExportPreview([
            'target_group_job_id' => $jobId,
            'categories' => ['no_history'],
        ]);

        $this->assertSame(['no_history'], $preview['selected_filter_summary']['categories']);
        $this->assertSame(1, $preview['total_stored_result_rows']);
        $this->assertSame(0, $preview['category_counts']['has_history']);
        $this->assertSame(1, $preview['category_counts']['no_history']);
        $this->assertSame(0, $preview['category_counts']['needs_review']);
    }

    private function createTargetGroupJob(string $name = 'synthetic-target-group'): int
    {
        return DB::table('target_group_jobs')->insertGetId([
            'group_name' => $name,
            'status' => 'synthetic_ready',
            'total_files' => 0,
            'total_rows' => 0,
            'valid_rows' => 0,
            'invalid_rows' => 0,
            'review_rows' => 0,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function createResultGenerationJob(int $targetGroupJobId): int
    {
        return DB::table('result_generation_jobs')->insertGetId([
            'target_group_job_id' => $targetGroupJobId,
            'status' => 'completed',
            'selected_service_keys' => json_encode(['synthetic-service']),
            'normalization_version' => 1,
            'total_persons' => 1,
            'completed_persons' => 1,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function createResult(int $targetGroupJobId, int $resultGenerationJobId, string $category): int
    {
        return DB::table('target_group_results')->insertGetId([
            'target_group_job_id' => $targetGroupJobId,
            'result_generation_job_id' => $resultGenerationJobId,
            'person_key' => 'synthetic-person-'.uniqid(),
            'result_category' => $category,
            'has_screening_db_history' => $category === 'has_history',
            'has_target_group_file_history' => false,
            'has_any_history' => $category === 'has_history',
            'selected_service_keys' => json_encode(['synthetic-service']),
            'evidence_summary' => json_encode(['sources' => []]),
            'review_status' => 'not_required',
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function createSource(int $targetGroupResultId): void
    {
        DB::table('target_group_result_sources')->insert([
            'target_group_result_id' => $targetGroupResultId,
            'source_type' => 'synthetic_source',
            'source_payload' => json_encode(['synthetic' => true]),
            'provenance' => json_encode(['reference' => 'synthetic-reference']),
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }
}
