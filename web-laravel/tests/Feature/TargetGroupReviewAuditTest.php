<?php

namespace Tests\Feature;

use App\Models\TargetGroupRow;
use App\Models\User;
use App\Models\TargetGroupRowReview;
use App\Services\Review\TargetGroupReviewService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use LogicException;
use Tests\TestCase;

final class TargetGroupReviewAuditTest extends TestCase
{
    use RefreshDatabase;

    public function test_review_decision_appends_event_and_typed_masked_audit_evidence(): void
    {
        $actor = User::create([
            'name' => 'SYNTHETIC_AUDITOR',
            'email' => 'synthetic-auditor@example.invalid',
            'password' => 'technical-test-password',
        ]);
        $row = $this->createRow();
        $service = app(TargetGroupReviewService::class);
        $service->markNeedsReview($row, 'SOURCE_EVIDENCE_CONFLICT', [
            'correlation_id' => 'SYN-CORRELATION-REVIEW',
            'conflict_flags' => ['source_payload' => true],
        ]);
        $service->decide($row->fresh(), TargetGroupReviewService::OUTCOME_REJECTED, 'SOURCE_EVIDENCE_CONFLICT', [
            'actor_user_id' => $actor->id,
            'operator_note' => 'Synthetic evidence conflict rejected.',
            'correlation_id' => 'SYN-CORRELATION-REVIEW',
            'conflict_flags' => ['source_payload' => true],
        ]);

        $this->assertSame(2, TargetGroupRowReview::query()->count());
        $event = TargetGroupRowReview::query()->where('review_outcome', 'REJECTED')->firstOrFail();
        $this->assertSame($actor->id, $event->reviewed_by);
        $this->assertSame('SOURCE_EVIDENCE_CONFLICT', $event->review_reason_code);
        $this->assertSame('SYN-CORRELATION-REVIEW', $event->correlation_id);
        $this->assertSame('NEEDS_REVIEW', $event->from_status);
        $this->assertSame('REJECTED', $event->to_status);
        $this->assertSame('Synthetic evidence conflict rejected.', $event->operator_note);

        $audit = DB::table('audit_logs')->where('action', 'review_rejected')->first();
        $this->assertNotNull($audit);
        $this->assertSame('SYN-CORRELATION-REVIEW', $audit->correlation_id);
        $this->assertSame($row->id, $audit->target_group_row_id);
        $this->assertSame($actor->id, $audit->reviewed_by);
        $this->assertSame('SOURCE_EVIDENCE_CONFLICT', $audit->review_reason_code);
        $this->assertStringNotContainsString('1234567890121', (string) $audit->before_payload);
        $this->assertStringNotContainsString('1234567890121', (string) $audit->after_payload);
    }

    public function test_review_events_are_append_only(): void
    {
        $row = $this->createRow();
        $event = app(TargetGroupReviewService::class)->markNeedsReview($row, 'MISSING_CID');
        $reviewEvent = TargetGroupRowReview::query()->where('target_group_row_id', $event->id)->firstOrFail();

        $this->expectException(LogicException::class);
        $reviewEvent->update(['operator_note' => 'must not mutate history']);
    }

    private function createRow(): TargetGroupRow
    {
        $jobId = DB::table('target_group_jobs')->insertGetId([
            'group_name' => 'SYNTHETIC_AUDIT_GROUP',
            'status' => 'staged',
            'total_files' => 1,
            'total_rows' => 1,
            'valid_rows' => 0,
            'invalid_rows' => 1,
            'review_rows' => 1,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        $fileId = DB::table('target_group_files')->insertGetId([
            'target_group_job_id' => $jobId,
            'original_filename' => 'synthetic.csv',
            'stored_path' => 'synthetic/audit.csv',
            'mime_type' => 'text/csv',
            'size_bytes' => 1,
            'sha256' => hash('sha256', 'synthetic-audit-'.$jobId),
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return TargetGroupRow::query()->create([
            'target_group_job_id' => $jobId,
            'target_group_file_id' => $fileId,
            'sheet_name' => 'SYNTHETIC',
            'row_number' => 1,
            'raw_payload' => ['source' => 'synthetic-audit-test'],
            'raw_cid' => '1234567890121',
            'normalized_cid' => '1234567890121',
            'cid_status' => 'valid',
            'raw_full_name' => 'SYNTHETIC_AUDIT_NAME',
            'normalized_full_name' => 'SYNTHETIC_AUDIT_NAME',
            'raw_birth_date' => '2000-01-01',
            'normalized_birth_date' => '2000-01-01',
            'validation_status' => 'invalid',
            'review_reason' => 'Synthetic review',
        ]);
    }
}
