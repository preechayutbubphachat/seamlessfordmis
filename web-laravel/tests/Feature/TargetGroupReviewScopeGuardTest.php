<?php

namespace Tests\Feature;

use App\Models\TargetGroupRow;
use App\Services\Import\TargetGroupImportService;
use App\Services\Review\TargetGroupReviewService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use LogicException;
use Tests\TestCase;

final class TargetGroupReviewScopeGuardTest extends TestCase
{
    use RefreshDatabase;

    public function test_only_scope_zero_current_import_context_is_allowed(): void
    {
        $service = app(TargetGroupReviewService::class);

        $service->assertScopeSafe(['matching_scope' => 'current_import']);

        $this->expectException(LogicException::class);
        $service->assertScopeSafe([
            'matching_scope' => 'persisted_program',
            'program_id' => 'SYN_PROGRAM_B',
        ]);
    }

    public function test_cross_hospital_and_cross_program_contexts_fail_closed(): void
    {
        $service = app(TargetGroupReviewService::class);

        try {
            $service->assertScopeSafe(['hospital_id' => 'SYN_HOSPITAL_B']);
            $this->fail('Cross-hospital scope must be blocked.');
        } catch (LogicException $exception) {
            $this->assertStringContainsString('scope', strtolower($exception->getMessage()));
        }

        $this->expectException(LogicException::class);
        $service->assertScopeSafe(['program_id' => 'SYN_PROGRAM_B']);
    }

    public function test_deferred_reason_cannot_be_activated_and_durable_stage_stays_blocked(): void
    {
        $row = $this->createRow();
        $service = app(TargetGroupReviewService::class);

        $this->expectException(\InvalidArgumentException::class);
        $service->markNeedsReview($row, 'PROGRAM_SCOPE_CONFLICT');
    }

    public function test_target_group_stage_remains_placeholder_and_writes_nothing(): void
    {
        $this->expectException(LogicException::class);
        app(TargetGroupImportService::class)->stage([]);
    }

    private function createRow(): TargetGroupRow
    {
        $jobId = DB::table('target_group_jobs')->insertGetId([
            'group_name' => 'SYNTHETIC_SCOPE_GROUP',
            'status' => 'staged',
            'total_files' => 0,
            'total_rows' => 0,
            'valid_rows' => 0,
            'invalid_rows' => 0,
            'review_rows' => 0,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        $fileId = DB::table('target_group_files')->insertGetId([
            'target_group_job_id' => $jobId,
            'original_filename' => 'synthetic.csv',
            'stored_path' => 'synthetic/scope.csv',
            'mime_type' => 'text/csv',
            'size_bytes' => 1,
            'sha256' => hash('sha256', 'synthetic-scope-'.$jobId),
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return TargetGroupRow::query()->create([
            'target_group_job_id' => $jobId,
            'target_group_file_id' => $fileId,
            'sheet_name' => 'SYNTHETIC',
            'row_number' => 1,
            'raw_payload' => ['source' => 'synthetic-scope-test'],
            'raw_cid' => '1234567890121',
            'normalized_cid' => '1234567890121',
            'cid_status' => 'valid',
            'validation_status' => 'valid',
        ]);
    }
}
