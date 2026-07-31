<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class TargetGroupResultsReviewTest extends TestCase
{
    use RefreshDatabase;

    public function test_results_page_returns_success(): void
    {
        $targetGroupJobId = $this->createSyntheticTargetGroupJob();

        $this->get("/target-groups/{$targetGroupJobId}/results")
            ->assertOk()
            ->assertSee('Target Group Results');
    }

    public function test_empty_result_page_shows_no_records_message(): void
    {
        $targetGroupJobId = $this->createSyntheticTargetGroupJob();

        $this->get("/target-groups/{$targetGroupJobId}/results")
            ->assertOk()
            ->assertSee('No stored results yet');
    }

    public function test_page_lists_synthetic_stored_result(): void
    {
        $targetGroupJobId = $this->createSyntheticTargetGroupJob();
        $resultGenerationJobId = $this->createSyntheticResultGenerationJob($targetGroupJobId);

        DB::table('target_group_results')->insert([
            'target_group_job_id' => $targetGroupJobId,
            'result_generation_job_id' => $resultGenerationJobId,
            'person_key' => 'synthetic-result-alpha',
            'result_category' => 'has_history',
            'has_screening_db_history' => true,
            'has_target_group_file_history' => false,
            'has_any_history' => true,
            'latest_history_date' => '2026-01-15',
            'latest_history_source' => 'screening_db',
            'selected_service_keys' => json_encode(['alpha']),
            'evidence_summary' => json_encode(['sources' => [['source_type' => 'screening_db']]]),
            'review_status' => 'not_required',
            'review_reason' => 'synthetic review note',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $this->get("/target-groups/{$targetGroupJobId}/results")
            ->assertOk()
            ->assertSee('has_history')
            ->assertSee('not_required')
            ->assertSee('synthetic review note')
            ->assertSee('2026-01-15')
            ->assertSee('screening_db');
    }

    public function test_evidence_and_provenance_detail_visible_for_synthetic_result(): void
    {
        $targetGroupJobId = $this->createSyntheticTargetGroupJob();
        $resultGenerationJobId = $this->createSyntheticResultGenerationJob($targetGroupJobId);
        $targetGroupResultId = DB::table('target_group_results')->insertGetId([
            'target_group_job_id' => $targetGroupJobId,
            'result_generation_job_id' => $resultGenerationJobId,
            'person_key' => 'synthetic-result-beta',
            'result_category' => 'has_history',
            'has_screening_db_history' => false,
            'has_target_group_file_history' => true,
            'has_any_history' => true,
            'latest_history_date' => '2026-02-20',
            'latest_history_source' => 'target_group_file',
            'selected_service_keys' => json_encode(['alpha']),
            'evidence_summary' => json_encode(['sources' => [['source_type' => 'target_group_file', 'provenance' => ['reference' => 'synthetic-summary-ref']]]]),
            'review_status' => 'not_required',
            'review_reason' => null,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        DB::table('target_group_result_sources')->insert([
            'target_group_result_id' => $targetGroupResultId,
            'source_type' => 'target_group_file',
            'source_payload' => json_encode(['synthetic_source_value' => 'visible']),
            'evidence_date' => '2026-02-20',
            'normalized_service_key' => 'alpha',
            'provenance' => json_encode(['reference' => 'synthetic-source-ref']),
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $this->get("/target-groups/{$targetGroupJobId}/results")
            ->assertOk()
            ->assertSee('target_group_file')
            ->assertSee('synthetic-summary-ref')
            ->assertSee('synthetic_source_value')
            ->assertSee('synthetic-source-ref');
    }

    public function test_get_results_page_does_not_write_records(): void
    {
        $targetGroupJobId = $this->createSyntheticTargetGroupJob();
        $resultGenerationJobId = $this->createSyntheticResultGenerationJob($targetGroupJobId);
        DB::table('target_group_results')->insert([
            'target_group_job_id' => $targetGroupJobId,
            'result_generation_job_id' => $resultGenerationJobId,
            'person_key' => 'synthetic-result-gamma',
            'result_category' => 'no_history',
            'has_screening_db_history' => false,
            'has_target_group_file_history' => false,
            'has_any_history' => false,
            'selected_service_keys' => json_encode(['alpha']),
            'evidence_summary' => json_encode(['sources' => []]),
            'review_status' => 'not_required',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $countsBefore = $this->resultTableCounts();

        $this->get("/target-groups/{$targetGroupJobId}/results")->assertOk();

        $this->assertSame($countsBefore, $this->resultTableCounts());
    }

    private function createSyntheticTargetGroupJob(): int
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

    private function createSyntheticResultGenerationJob(int $targetGroupJobId): int
    {
        return DB::table('result_generation_jobs')->insertGetId([
            'target_group_job_id' => $targetGroupJobId,
            'status' => 'drafted',
            'selected_service_keys' => json_encode(['alpha']),
            'normalization_version' => 1,
            'total_persons' => 1,
            'completed_persons' => 1,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function resultTableCounts(): array
    {
        return [
            'result_generation_jobs' => DB::table('result_generation_jobs')->count(),
            'target_group_results' => DB::table('target_group_results')->count(),
            'target_group_result_sources' => DB::table('target_group_result_sources')->count(),
        ];
    }
}
