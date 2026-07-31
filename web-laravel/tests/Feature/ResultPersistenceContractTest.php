<?php

namespace Tests\Feature;

use App\Services\Result\ResultGenerationService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;
use Tests\TestCase;

final class ResultPersistenceContractTest extends TestCase
{
    use RefreshDatabase;

    private ResultGenerationService $service;

    protected function setUp(): void
    {
        parent::setUp();

        $this->service = new ResultGenerationService();
    }

    public function test_persisting_drafts_creates_one_result_generation_job(): void
    {
        $targetGroupJobId = $this->createSyntheticTargetGroupJob();

        $summary = $this->service->persistResultDraftsForJob($targetGroupJobId, [
            $this->draft('person-a', ResultGenerationService::CATEGORY_HAS_HISTORY),
        ], ['selected_service_keys' => ['alpha']]);

        $this->assertSame(1, $summary['result_generation_job_id']);
        $this->assertSame(1, DB::table('result_generation_jobs')->count());
        $this->assertDatabaseHas('result_generation_jobs', [
            'id' => $summary['result_generation_job_id'],
            'target_group_job_id' => $targetGroupJobId,
            'status' => 'drafted',
            'total_persons' => 1,
            'completed_persons' => 1,
        ]);
    }

    public function test_persisting_drafts_writes_one_result_per_person_key(): void
    {
        $targetGroupJobId = $this->createSyntheticTargetGroupJob();

        $this->service->persistResultDraftsForJob($targetGroupJobId, [
            $this->draft('person-a', ResultGenerationService::CATEGORY_HAS_HISTORY),
            $this->draft('person-b', ResultGenerationService::CATEGORY_NO_HISTORY),
        ], ['selected_service_keys' => ['alpha']]);

        $this->assertSame(2, DB::table('target_group_results')->count());
        $this->assertDatabaseHas('target_group_results', ['person_key' => 'person-a']);
        $this->assertDatabaseHas('target_group_results', ['person_key' => 'person-b']);
    }

    public function test_persisting_drafts_writes_result_sources_with_provenance(): void
    {
        $targetGroupJobId = $this->createSyntheticTargetGroupJob();

        $this->service->persistResultDraftsForJob($targetGroupJobId, [
            $this->draft('person-a', ResultGenerationService::CATEGORY_HAS_HISTORY),
        ], ['selected_service_keys' => ['alpha']]);

        $this->assertSame(1, DB::table('target_group_result_sources')->count());
        $source = DB::table('target_group_result_sources')->first();

        $this->assertSame('target_group_file', $source->source_type);
        $this->assertStringContainsString('synthetic-ref-person-a', $source->provenance);
        $this->assertStringContainsString('synthetic-source-person-a', $source->source_payload);
    }

    public function test_invalid_identifier_persists_as_invalid_identifier_not_no_history(): void
    {
        $targetGroupJobId = $this->createSyntheticTargetGroupJob();

        $this->service->persistResultDraftsForJob($targetGroupJobId, [
            $this->draft('person-invalid', ResultGenerationService::CATEGORY_INVALID_IDENTIFIER),
        ], ['selected_service_keys' => ['alpha']]);

        $this->assertDatabaseHas('target_group_results', [
            'person_key' => 'person-invalid',
            'result_category' => ResultGenerationService::CATEGORY_INVALID_IDENTIFIER,
        ]);
        $this->assertDatabaseMissing('target_group_results', [
            'person_key' => 'person-invalid',
            'result_category' => ResultGenerationService::CATEGORY_NO_HISTORY,
        ]);
    }

    public function test_missing_identifier_persists_as_missing_identifier_not_no_history(): void
    {
        $targetGroupJobId = $this->createSyntheticTargetGroupJob();

        $this->service->persistResultDraftsForJob($targetGroupJobId, [
            $this->draft('person-missing', ResultGenerationService::CATEGORY_MISSING_IDENTIFIER),
        ], ['selected_service_keys' => ['alpha']]);

        $this->assertDatabaseHas('target_group_results', [
            'person_key' => 'person-missing',
            'result_category' => ResultGenerationService::CATEGORY_MISSING_IDENTIFIER,
        ]);
        $this->assertDatabaseMissing('target_group_results', [
            'person_key' => 'person-missing',
            'result_category' => ResultGenerationService::CATEGORY_NO_HISTORY,
        ]);
    }

    public function test_transaction_rolls_back_on_malformed_draft(): void
    {
        $targetGroupJobId = $this->createSyntheticTargetGroupJob();

        try {
            $this->service->persistResultDraftsForJob($targetGroupJobId, [
                $this->draft('person-a', ResultGenerationService::CATEGORY_HAS_HISTORY),
                ['result_category' => ResultGenerationService::CATEGORY_HAS_HISTORY],
            ], ['selected_service_keys' => ['alpha']]);

            $this->fail('Malformed draft should throw.');
        } catch (InvalidArgumentException $exception) {
            $this->assertStringContainsString('person_key', $exception->getMessage());
        }

        $this->assertSame(0, DB::table('result_generation_jobs')->count());
        $this->assertSame(0, DB::table('target_group_results')->count());
        $this->assertSame(0, DB::table('target_group_result_sources')->count());
    }

    public function test_retry_replaces_existing_results_for_same_job_without_duplicates(): void
    {
        $targetGroupJobId = $this->createSyntheticTargetGroupJob();

        $this->service->persistResultDraftsForJob($targetGroupJobId, [
            $this->draft('person-a', ResultGenerationService::CATEGORY_HAS_HISTORY),
        ], ['selected_service_keys' => ['alpha']]);

        $this->service->persistResultDraftsForJob($targetGroupJobId, [
            $this->draft('person-a', ResultGenerationService::CATEGORY_NO_HISTORY),
        ], ['selected_service_keys' => ['alpha']]);

        $this->assertSame(1, DB::table('result_generation_jobs')->count());
        $this->assertSame(1, DB::table('target_group_results')->count());
        $this->assertDatabaseHas('target_group_results', [
            'person_key' => 'person-a',
            'result_category' => ResultGenerationService::CATEGORY_NO_HISTORY,
        ]);
        $this->assertSame(0, DB::table('target_group_result_sources')->count());
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

    private function draft(string $personKey, string $category): array
    {
        return [
            'person_key' => $personKey,
            'normalized_cid' => null,
            'result_category' => $category,
            'has_screening_db_history' => false,
            'has_target_group_file_history' => $category === ResultGenerationService::CATEGORY_HAS_HISTORY,
            'has_any_history' => $category === ResultGenerationService::CATEGORY_HAS_HISTORY,
            'latest_history_date' => $category === ResultGenerationService::CATEGORY_HAS_HISTORY ? '2026-01-15' : null,
            'latest_history_source' => $category === ResultGenerationService::CATEGORY_HAS_HISTORY ? 'target_group_file' : null,
            'selected_service_keys' => ['alpha'],
            'evidence_summary' => [
                'sources' => $category === ResultGenerationService::CATEGORY_HAS_HISTORY ? [[
                    'source_type' => 'target_group_file',
                    'source_payload' => ['synthetic_source' => 'synthetic-source-' . $personKey],
                    'evidence_date' => '2026-01-15',
                    'normalized_service_key' => 'alpha',
                    'provenance' => ['reference' => 'synthetic-ref-' . $personKey],
                ]] : [],
            ],
            'review_status' => $category === ResultGenerationService::CATEGORY_NEEDS_REVIEW ? 'needs_review' : 'not_required',
            'review_reason' => null,
        ];
    }
}
