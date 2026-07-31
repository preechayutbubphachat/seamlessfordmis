<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

final class ExportPreviewContractTest extends TestCase
{
    use RefreshDatabase;

    public function test_export_preview_page_returns_success(): void
    {
        $this->get('/exports/preview')
            ->assertOk()
            ->assertSee('Export Eligibility Preview')
            ->assertSee('Export file generation is not enabled yet.')
            ->assertSee('No export preview loaded');
    }

    public function test_unknown_job_returns_controlled_validation_response(): void
    {
        $this->from('/exports/preview')->post('/exports/preview', [
            'target_group_job_id' => 999999,
        ])->assertRedirect('/exports/preview')
            ->assertSessionHasErrors('target_group_job_id');
    }

    public function test_existing_export_post_remains_disabled(): void
    {
        Storage::fake('local');

        $this->post('/exports', ['export_type' => 'result_review'])
            ->assertStatus(501)
            ->assertJson([
                'message' => 'Export generation is not enabled yet.',
                'file_created' => false,
            ]);

        Storage::disk('local')->assertMissing('exports/result_review.csv');
        Storage::disk('local')->assertMissing('exports/result_review.xlsx');
    }

    public function test_preview_for_job_with_stored_results_shows_aggregate_counts_only(): void
    {
        $jobId = $this->createTargetGroupJob();
        $resultJobId = $this->createResultGenerationJob($jobId);
        $hasHistoryResultId = $this->createResult($jobId, $resultJobId, 'has_history', [
            'display_name' => 'SYNTHETIC_PRIVATE_LABEL_DO_NOT_RENDER',
            'normalized_cid' => 'SYNTHETICCID1',
        ]);
        $this->createResult($jobId, $resultJobId, 'no_history');
        $this->createResult($jobId, $resultJobId, 'needs_review');
        $this->createSource($hasHistoryResultId);
        $this->createSource($hasHistoryResultId);

        $response = $this->post('/exports/preview', [
            'target_group_job_id' => $jobId,
        ]);

        $response
            ->assertOk()
            ->assertSee('eligible')
            ->assertSee('total stored result row count')
            ->assertSee('has_history')
            ->assertSee('no_history')
            ->assertSee('invalid_identifier')
            ->assertSee('missing_identifier')
            ->assertSee('needs_review')
            ->assertSee('result source/provenance availability count')
            ->assertDontSee('SYNTHETIC_PRIVATE_LABEL_DO_NOT_RENDER')
            ->assertDontSee('SYNTHETICCID1')
            ->assertDontSee('RAW_PAYLOAD_TOKEN_DO_NOT_RENDER')
            ->assertDontSee('Download');
    }

    public function test_staging_rows_alone_are_not_export_eligible(): void
    {
        $jobId = $this->createTargetGroupJob();
        $this->createTargetGroupStagingRow($jobId);

        $this->post('/exports/preview', [
            'target_group_job_id' => $jobId,
        ])->assertOk()
            ->assertSee('not_eligible')
            ->assertSee('no_stored_results')
            ->assertSee('total stored result row count')
            ->assertSee('>0<', false);
    }

    public function test_preview_filters_result_generation_job_and_category(): void
    {
        $jobId = $this->createTargetGroupJob();
        $firstResultJobId = $this->createResultGenerationJob($jobId);
        $secondResultJobId = $this->createResultGenerationJob($jobId);
        $this->createResult($jobId, $firstResultJobId, 'has_history');
        $this->createResult($jobId, $secondResultJobId, 'missing_identifier');

        $this->post('/exports/preview', [
            'result_generation_job_id' => $secondResultJobId,
            'categories' => ['missing_identifier'],
        ])->assertOk()
            ->assertSee('missing_identifier')
            ->assertSee('"result_generation_job_id": '.$secondResultJobId)
            ->assertSee('"categories": [')
            ->assertSee('>1<', false);
    }

    public function test_preview_get_and_post_create_no_rows(): void
    {
        Storage::fake('local');
        $jobId = $this->createTargetGroupJob();
        $resultJobId = $this->createResultGenerationJob($jobId);
        $this->createResult($jobId, $resultJobId, 'has_history');
        $before = $this->tableCounts();

        $this->get('/exports/preview')->assertOk();
        $this->post('/exports/preview', [
            'target_group_job_id' => $jobId,
        ])->assertOk();

        $this->assertSame($before, $this->tableCounts());
        Storage::disk('local')->assertMissing('exports/result_review.csv');
        Storage::disk('local')->assertMissing('exports/result_review.xlsx');
    }

    public function test_invalid_category_filter_is_rejected(): void
    {
        $jobId = $this->createTargetGroupJob();

        $this->from('/exports/preview')->post('/exports/preview', [
            'target_group_job_id' => $jobId,
            'categories' => ['not_allowed'],
        ])->assertRedirect('/exports/preview')
            ->assertSessionHasErrors('categories.0');
    }

    private function createTargetGroupJob(): int
    {
        return DB::table('target_group_jobs')->insertGetId([
            'group_name' => 'synthetic-target-group',
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

    private function createResult(int $targetGroupJobId, int $resultGenerationJobId, string $category, array $overrides = []): int
    {
        return DB::table('target_group_results')->insertGetId(array_merge([
            'target_group_job_id' => $targetGroupJobId,
            'result_generation_job_id' => $resultGenerationJobId,
            'person_key' => 'synthetic-person-'.uniqid(),
            'display_name' => null,
            'normalized_cid' => null,
            'result_category' => $category,
            'has_screening_db_history' => $category === 'has_history',
            'has_target_group_file_history' => false,
            'has_any_history' => $category === 'has_history',
            'selected_service_keys' => json_encode(['synthetic-service']),
            'evidence_summary' => json_encode(['sources' => []]),
            'review_status' => 'not_required',
            'created_at' => now(),
            'updated_at' => now(),
        ], $overrides));
    }

    private function createSource(int $targetGroupResultId): void
    {
        DB::table('target_group_result_sources')->insert([
            'target_group_result_id' => $targetGroupResultId,
            'source_type' => 'synthetic_source',
            'source_payload' => json_encode(['raw_payload' => 'RAW_PAYLOAD_TOKEN_DO_NOT_RENDER']),
            'provenance' => json_encode(['reference' => 'synthetic-reference']),
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function createTargetGroupStagingRow(int $jobId): void
    {
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
    }

    private function tableCounts(): array
    {
        return [
            'export_jobs' => DB::table('export_jobs')->count(),
            'audit_logs' => DB::table('audit_logs')->count(),
            'target_group_results' => DB::table('target_group_results')->count(),
            'target_group_result_sources' => DB::table('target_group_result_sources')->count(),
            'source_import_jobs' => DB::table('source_import_jobs')->count(),
            'source_import_rows' => DB::table('source_import_rows')->count(),
            'target_group_jobs' => DB::table('target_group_jobs')->count(),
            'target_group_rows' => DB::table('target_group_rows')->count(),
        ];
    }
}
