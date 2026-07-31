<?php

namespace Tests\Feature;

use App\Services\Result\ResultGenerationService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class StagedToResultDraftContractTest extends TestCase
{
    use RefreshDatabase;

    private ResultGenerationService $service;

    protected function setUp(): void
    {
        parent::setUp();

        $this->service = new ResultGenerationService();
    }

    public function test_staged_target_row_with_source_history_has_history(): void
    {
        $target = $this->createTargetGroupRow('1234567890121');
        $this->createSourceImportRow('1234567890121', 'alpha', '2026-01-10');

        $drafts = $this->service->buildDraftsFromTargetGroupJob($target['job_id'], ['alpha']);

        $this->assertCount(1, $drafts);
        $this->assertSame(ResultGenerationService::CATEGORY_HAS_HISTORY, $drafts[0]['result_category']);
        $this->assertTrue($drafts[0]['has_screening_db_history']);
        $this->assertFalse($drafts[0]['has_target_group_file_history']);
        $this->assertSame('2026-01-10', $drafts[0]['latest_history_date']);
        $this->assertSame('screening_db', $drafts[0]['latest_history_source']);
    }

    public function test_staged_target_row_with_target_group_file_history_has_history(): void
    {
        $target = $this->createTargetGroupRow('1234567890121');
        $this->createTargetGroupHistoryRow($target, 'alpha', '2026-02-03');

        $drafts = $this->service->buildDraftsFromTargetGroupJob($target['job_id'], ['alpha']);

        $this->assertSame(ResultGenerationService::CATEGORY_HAS_HISTORY, $drafts[0]['result_category']);
        $this->assertFalse($drafts[0]['has_screening_db_history']);
        $this->assertTrue($drafts[0]['has_target_group_file_history']);
        $this->assertSame('target_group_file', $drafts[0]['latest_history_source']);
    }

    public function test_staged_target_row_with_no_selected_service_history_is_no_history(): void
    {
        $target = $this->createTargetGroupRow('1234567890121');
        $this->createTargetGroupHistoryRow($target, 'beta', '2026-03-01');

        $drafts = $this->service->buildDraftsFromTargetGroupJob($target['job_id'], ['alpha']);

        $this->assertSame(ResultGenerationService::CATEGORY_NO_HISTORY, $drafts[0]['result_category']);
        $this->assertFalse($drafts[0]['has_any_history']);
        $this->assertNull($drafts[0]['latest_history_date']);
    }

    public function test_invalid_and_missing_cid_are_not_no_history(): void
    {
        $invalid = $this->createTargetGroupRow('1234567890129');
        $missing = $this->createTargetGroupRow(null, $invalid['job_id'], $invalid['file_id']);

        $drafts = $this->service->buildDraftsFromTargetGroupJob($invalid['job_id'], ['alpha']);

        $this->assertCount(2, $drafts);
        $this->assertSame(ResultGenerationService::CATEGORY_INVALID_IDENTIFIER, $drafts[0]['result_category']);
        $this->assertSame(ResultGenerationService::CATEGORY_MISSING_IDENTIFIER, $drafts[1]['result_category']);
        $this->assertNotContains(ResultGenerationService::CATEGORY_NO_HISTORY, array_column($drafts, 'result_category'));
        $this->assertNotNull($missing['row_id']);
    }

    public function test_latest_date_uses_selected_service_only_and_ignores_unrelated_service(): void
    {
        $target = $this->createTargetGroupRow('1234567890121');
        $this->createSourceImportRow('1234567890121', 'alpha', '2026-01-10');
        $this->createSourceImportRow('1234567890121', 'beta', '2026-12-31');
        $this->createTargetGroupHistoryRow($target, 'alpha', '2026-02-03');

        $drafts = $this->service->buildDraftsFromTargetGroupJob($target['job_id'], ['alpha']);

        $this->assertSame('2026-02-03', $drafts[0]['latest_history_date']);
        $this->assertSame('target_group_file', $drafts[0]['latest_history_source']);
        $this->assertCount(2, $drafts[0]['evidence_summary']['sources']);
        $this->assertNotContains('beta', array_column($drafts[0]['evidence_summary']['sources'], 'normalized_service_key'));
    }

    public function test_one_draft_per_cid_and_ambiguous_identity_needs_review(): void
    {
        $first = $this->createTargetGroupRow('1234567890121', null, null, 'SYN_ALPHA');
        $this->createTargetGroupRow('1234567890121', $first['job_id'], $first['file_id'], 'SYN_BETA');

        $drafts = $this->service->buildDraftsFromTargetGroupJob($first['job_id'], ['alpha']);

        $this->assertCount(1, $drafts);
        $this->assertSame('cid:1234567890121', $drafts[0]['person_key']);
        $this->assertSame(ResultGenerationService::CATEGORY_NEEDS_REVIEW, $drafts[0]['result_category']);
        $this->assertSame('needs_review', $drafts[0]['review_status']);
    }

    public function test_provenance_references_staging_rows_and_building_drafts_writes_no_results(): void
    {
        $target = $this->createTargetGroupRow('1234567890121');
        $sourceRowId = $this->createSourceImportRow('1234567890121', 'alpha', '2026-01-10');
        $historyRowId = $this->createTargetGroupHistoryRow($target, 'alpha', '2026-02-03');

        $before = [
            'result_generation_jobs' => DB::table('result_generation_jobs')->count(),
            'target_group_results' => DB::table('target_group_results')->count(),
            'target_group_result_sources' => DB::table('target_group_result_sources')->count(),
        ];

        $drafts = $this->service->buildDraftsFromTargetGroupJob($target['job_id'], ['alpha']);

        $this->assertSame($before['result_generation_jobs'], DB::table('result_generation_jobs')->count());
        $this->assertSame($before['target_group_results'], DB::table('target_group_results')->count());
        $this->assertSame($before['target_group_result_sources'], DB::table('target_group_result_sources')->count());

        $sources = $drafts[0]['evidence_summary']['sources'];
        $this->assertSame('source_import_rows', $sources[0]['provenance']['table']);
        $this->assertSame($sourceRowId, $sources[0]['provenance']['row_id']);
        $this->assertSame('target_group_history_rows', $sources[1]['provenance']['table']);
        $this->assertSame($historyRowId, $sources[1]['provenance']['row_id']);
        $this->assertSame([$target['row_id']], $drafts[0]['target_group_row_ids']);
    }

    private function createTargetGroupRow(?string $cid, ?int $jobId = null, ?int $fileId = null, string $name = 'SYN_ALPHA'): array
    {
        $now = now();
        $jobId ??= DB::table('target_group_jobs')->insertGetId([
            'group_name' => 'synthetic-target-group',
            'status' => 'preview_staged',
            'total_files' => 1,
            'total_rows' => 0,
            'valid_rows' => 0,
            'invalid_rows' => 0,
            'review_rows' => 0,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        $fileId ??= DB::table('target_group_files')->insertGetId([
            'target_group_job_id' => $jobId,
            'original_filename' => 'synthetic-preview.csv',
            'stored_path' => '__synthetic_preview_no_file_stored__',
            'mime_type' => 'text/csv',
            'size_bytes' => 0,
            'sha256' => hash('sha256', 'target-'.$jobId.'-'.$name),
            'row_count' => 0,
            'created_at' => $now,
            'updated_at' => $now,
        ]);

        $status = $cid === null ? 'missing_identifier' : ($cid === '1234567890121' ? 'valid' : 'invalid_identifier');
        $rowNumber = (int) DB::table('target_group_rows')->where('target_group_job_id', $jobId)->count() + 2;
        $rowId = DB::table('target_group_rows')->insertGetId([
            'target_group_job_id' => $jobId,
            'target_group_file_id' => $fileId,
            'sheet_name' => 'synthetic-sheet',
            'row_number' => $rowNumber,
            'raw_payload' => json_encode(['cid' => $cid ?? '', 'full_name' => $name, 'marker' => 'TARGET_SYN']),
            'raw_cid' => $cid,
            'normalized_cid' => $status === 'valid' ? $cid : null,
            'cid_status' => $status,
            'raw_full_name' => $name,
            'normalized_full_name' => $name,
            'raw_birth_date' => null,
            'normalized_birth_date' => null,
            'validation_status' => $status,
            'review_reason' => null,
            'created_at' => $now,
            'updated_at' => $now,
        ]);

        return ['job_id' => $jobId, 'file_id' => $fileId, 'row_id' => $rowId];
    }

    private function createSourceImportRow(string $cid, string $serviceKey, string $visitDate): int
    {
        $now = now();
        $jobId = DB::table('source_import_jobs')->insertGetId([
            'job_name' => 'synthetic-source',
            'status' => 'preview_staged',
            'total_files' => 1,
            'total_rows' => 1,
            'valid_rows' => 1,
            'invalid_rows' => 0,
            'review_rows' => 0,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        $fileId = DB::table('source_import_files')->insertGetId([
            'source_import_job_id' => $jobId,
            'original_filename' => 'synthetic-source.csv',
            'stored_path' => '__synthetic_preview_no_file_stored__',
            'mime_type' => 'text/csv',
            'size_bytes' => 0,
            'sha256' => hash('sha256', 'source-'.$cid.'-'.$serviceKey.'-'.$visitDate),
            'row_count' => 1,
            'created_at' => $now,
            'updated_at' => $now,
        ]);

        return DB::table('source_import_rows')->insertGetId([
            'source_import_job_id' => $jobId,
            'source_file_id' => $fileId,
            'sheet_name' => 'synthetic-sheet',
            'row_number' => 2,
            'raw_payload' => json_encode(['cid' => $cid, 'service_key' => $serviceKey, 'visit_date' => $visitDate]),
            'raw_cid' => $cid,
            'normalized_cid' => $cid,
            'cid_status' => 'valid',
            'raw_full_name' => null,
            'normalized_full_name' => null,
            'raw_service_text' => $serviceKey,
            'normalized_service_key' => $serviceKey,
            'raw_visit_date' => $visitDate,
            'normalized_visit_date' => $visitDate,
            'validation_status' => 'valid',
            'review_reason' => null,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
    }

    private function createTargetGroupHistoryRow(array $target, string $serviceKey, string $visitDate): int
    {
        $now = now();

        return DB::table('target_group_history_rows')->insertGetId([
            'target_group_job_id' => $target['job_id'],
            'target_group_row_id' => $target['row_id'],
            'target_group_file_id' => $target['file_id'],
            'sheet_name' => 'synthetic-history',
            'row_number' => 20,
            'raw_payload' => json_encode(['service_key' => $serviceKey, 'visit_date' => $visitDate]),
            'raw_service_text' => $serviceKey,
            'normalized_service_key' => $serviceKey,
            'raw_visit_date' => $visitDate,
            'normalized_visit_date' => $visitDate,
            'evidence_source' => 'target_group_file',
            'provenance' => json_encode(['synthetic' => true]),
            'created_at' => $now,
            'updated_at' => $now,
        ]);
    }
}
