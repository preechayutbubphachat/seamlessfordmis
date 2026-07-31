<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

final class TargetGroupResultGenerationTriggerTest extends TestCase
{
    use RefreshDatabase;

    public function test_generate_without_confirmation_is_rejected(): void
    {
        $target = $this->createTargetGroupRow('1234567890121');

        $this->from('/target-groups/'.$target['job_id'])->post('/target-groups/'.$target['job_id'].'/generate-results', [
            'selected_service_keys' => ['alpha'],
        ])->assertRedirect('/target-groups/'.$target['job_id'])
            ->assertSessionHasErrors('confirmed');

        $this->assertSame(0, DB::table('result_generation_jobs')->count());
    }

    public function test_generate_with_empty_service_keys_is_rejected(): void
    {
        $target = $this->createTargetGroupRow('1234567890121');

        $this->from('/target-groups/'.$target['job_id'])->post('/target-groups/'.$target['job_id'].'/generate-results', [
            'selected_service_keys' => [],
            'confirmed' => '1',
        ])->assertRedirect('/target-groups/'.$target['job_id'])
            ->assertSessionHasErrors('selected_service_keys');

        $this->assertSame(0, DB::table('result_generation_jobs')->count());
    }

    public function test_generate_from_empty_staged_job_is_rejected(): void
    {
        $jobId = $this->createTargetGroupJob();

        $this->from('/target-groups/'.$jobId)->post('/target-groups/'.$jobId.'/generate-results', [
            'selected_service_keys' => ['alpha'],
            'confirmed' => '1',
        ])->assertRedirect('/target-groups/'.$jobId)
            ->assertSessionHasErrors('target_group_job');

        $this->assertSame(0, DB::table('result_generation_jobs')->count());
        $this->assertSame(0, DB::table('audit_logs')->count());
    }

    public function test_valid_staged_job_generates_results_sources_and_audit(): void
    {
        Storage::fake('local');
        $target = $this->createTargetGroupRow('1234567890121');
        $this->createSourceImportRow('1234567890121', 'alpha', '2026-01-10');
        $this->createTargetGroupHistoryRow($target, 'alpha', '2026-02-03');

        $this->post('/target-groups/'.$target['job_id'].'/generate-results', [
            'selected_service_keys' => ['alpha'],
            'confirmed' => '1',
        ])->assertRedirect('/target-groups/'.$target['job_id'].'/results');

        $this->assertSame(1, DB::table('result_generation_jobs')->count());
        $this->assertSame(1, DB::table('target_group_results')->count());
        $this->assertSame(2, DB::table('target_group_result_sources')->count());
        $this->assertDatabaseHas('target_group_results', [
            'target_group_job_id' => $target['job_id'],
            'result_category' => 'has_history',
            'latest_history_date' => '2026-02-03',
            'latest_history_source' => 'target_group_file',
        ]);
        $this->assertDatabaseHas('audit_logs', [
            'action' => 'result_generation_committed',
            'entity_type' => 'target_group_job',
            'entity_id' => $target['job_id'],
        ]);
        $this->assertNoExportOrStorageSideEffects();
    }

    public function test_invalid_and_missing_cid_categories_are_preserved(): void
    {
        $invalid = $this->createTargetGroupRow('1234567890129');
        $this->createTargetGroupRow(null, $invalid['job_id'], $invalid['file_id']);

        $this->post('/target-groups/'.$invalid['job_id'].'/generate-results', [
            'selected_service_keys' => ['alpha'],
            'confirmed' => '1',
        ])->assertRedirect('/target-groups/'.$invalid['job_id'].'/results');

        $this->assertDatabaseHas('target_group_results', [
            'result_category' => 'invalid_identifier',
        ]);
        $this->assertDatabaseHas('target_group_results', [
            'result_category' => 'missing_identifier',
        ]);
        $this->assertDatabaseMissing('target_group_results', [
            'result_category' => 'no_history',
        ]);
    }

    public function test_unrelated_service_is_ignored_and_target_group_file_history_is_evidence(): void
    {
        $target = $this->createTargetGroupRow('1234567890121');
        $this->createSourceImportRow('1234567890121', 'beta', '2026-12-31');
        $this->createTargetGroupHistoryRow($target, 'alpha', '2026-02-03');

        $this->post('/target-groups/'.$target['job_id'].'/generate-results', [
            'selected_service_keys' => ['alpha'],
            'confirmed' => '1',
        ])->assertRedirect('/target-groups/'.$target['job_id'].'/results');

        $this->assertDatabaseHas('target_group_results', [
            'result_category' => 'has_history',
            'latest_history_date' => '2026-02-03',
            'latest_history_source' => 'target_group_file',
        ]);
        $this->assertSame(1, DB::table('target_group_result_sources')->count());
        $this->assertDatabaseMissing('target_group_result_sources', [
            'normalized_service_key' => 'beta',
        ]);
    }

    public function test_retry_replaces_results_without_duplicate_stale_results(): void
    {
        $target = $this->createTargetGroupRow('1234567890121');
        $this->createTargetGroupHistoryRow($target, 'alpha', '2026-02-03');

        $this->post('/target-groups/'.$target['job_id'].'/generate-results', [
            'selected_service_keys' => ['alpha'],
            'confirmed' => '1',
        ])->assertRedirect('/target-groups/'.$target['job_id'].'/results');

        $this->post('/target-groups/'.$target['job_id'].'/generate-results', [
            'selected_service_keys' => ['alpha'],
            'confirmed' => '1',
        ])->assertRedirect('/target-groups/'.$target['job_id'].'/results');

        $this->assertSame(1, DB::table('result_generation_jobs')->count());
        $this->assertSame(1, DB::table('target_group_results')->count());
        $this->assertSame(1, DB::table('target_group_result_sources')->count());
        $this->assertSame(2, DB::table('audit_logs')->count());
    }

    public function test_target_group_detail_page_has_safe_generation_form_without_export_button(): void
    {
        $target = $this->createTargetGroupRow('1234567890121');

        $this->get('/target-groups/'.$target['job_id'])
            ->assertOk()
            ->assertSee('Generate Result Drafts')
            ->assertSee('selected_service_keys')
            ->assertSee('I confirm result generation should read staged data only')
            ->assertDontSee('Export Results')
            ->assertDontSee('Download');
    }

    private function createTargetGroupJob(): int
    {
        return DB::table('target_group_jobs')->insertGetId([
            'group_name' => 'synthetic-target-group',
            'status' => 'preview_staged',
            'total_files' => 1,
            'total_rows' => 0,
            'valid_rows' => 0,
            'invalid_rows' => 0,
            'review_rows' => 0,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function createTargetGroupRow(?string $cid, ?int $jobId = null, ?int $fileId = null): array
    {
        $now = now();
        $jobId ??= $this->createTargetGroupJob();
        $fileId ??= DB::table('target_group_files')->insertGetId([
            'target_group_job_id' => $jobId,
            'original_filename' => 'synthetic-preview.csv',
            'stored_path' => '__synthetic_preview_no_file_stored__',
            'mime_type' => 'text/csv',
            'size_bytes' => 0,
            'sha256' => hash('sha256', 'target-'.$jobId),
            'row_count' => 1,
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
            'raw_payload' => json_encode(['cid' => $cid ?? '', 'marker' => 'TARGET_SYN']),
            'raw_cid' => $cid,
            'normalized_cid' => $status === 'valid' ? $cid : null,
            'cid_status' => $status,
            'raw_full_name' => 'SYN_NAME',
            'normalized_full_name' => 'SYN_NAME',
            'raw_birth_date' => null,
            'normalized_birth_date' => null,
            'validation_status' => $status,
            'review_reason' => null,
            'created_at' => $now,
            'updated_at' => $now,
        ]);

        return ['job_id' => $jobId, 'file_id' => $fileId, 'row_id' => $rowId];
    }

    private function createSourceImportRow(string $cid, string $serviceKey, string $visitDate): void
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

        DB::table('source_import_rows')->insert([
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

    private function createTargetGroupHistoryRow(array $target, string $serviceKey, string $visitDate): void
    {
        DB::table('target_group_history_rows')->insert([
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
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function assertNoExportOrStorageSideEffects(): void
    {
        $this->assertSame(0, DB::table('export_jobs')->count());
        Storage::disk('local')->assertMissing('imports/synthetic.csv');
        Storage::disk('local')->assertMissing('exports/synthetic.csv');
        Storage::disk('local')->assertMissing('exports/synthetic.xlsx');
    }
}
