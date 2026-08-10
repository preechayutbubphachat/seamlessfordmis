<?php

namespace Tests\Feature;

use App\Models\TargetGroupRow;
use App\Models\User;
use App\Services\Review\TargetGroupReviewService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use LogicException;
use Tests\TestCase;

final class TargetGroupReviewTransitionTest extends TestCase
{
    use RefreshDatabase;

    public function test_valid_cid_is_valid_but_never_automatically_approved(): void
    {
        $row = $this->createRow([
            'raw_cid' => '1234567890121',
            'normalized_cid' => '1234567890121',
            'cid_status' => 'valid',
            'validation_status' => 'valid',
        ]);
        $service = app(TargetGroupReviewService::class);

        $valid = $service->markValid($row);

        $this->assertSame('VALID', $valid->review_status);
        $this->assertNull($valid->reviewed_by);
        $this->assertNotSame('APPROVED', $valid->review_status);
    }

    public function test_missing_cid_enters_needs_review_with_the_exact_reason(): void
    {
        $row = $this->createRow([
            'raw_cid' => null,
            'normalized_cid' => null,
            'cid_status' => 'missing_identifier',
            'validation_status' => 'invalid',
        ]);

        $reviewed = app(TargetGroupReviewService::class)->markNeedsReview($row, 'MISSING_CID');

        $this->assertSame('NEEDS_REVIEW', $reviewed->review_status);
        $this->assertSame('MISSING_CID', $reviewed->review_reason_code);
        $this->assertNull($reviewed->reviewed_by);
    }

    public function test_each_foundation_reason_enters_needs_review_without_silent_collapse(): void
    {
        $service = app(TargetGroupReviewService::class);

        foreach ($service->foundationReasonCodes() as $reasonCode) {
            $row = $this->createRow();
            $reviewed = $service->markNeedsReview($row, $reasonCode);

            $this->assertSame('NEEDS_REVIEW', $reviewed->review_status, $reasonCode);
            $this->assertSame($reasonCode, $reviewed->review_reason_code, $reasonCode);
        }

        $this->assertSame(9, DB::table('target_group_row_reviews')->where('to_status', 'NEEDS_REVIEW')->count());
        $this->assertSame(9, DB::table('target_group_rows')->where('review_status', 'NEEDS_REVIEW')->count());
    }

    public function test_only_explicit_operator_decision_can_leave_needs_review(): void
    {
        $actor = User::create([
            'name' => 'SYNTHETIC_REVIEWER',
            'email' => 'synthetic-reviewer@example.invalid',
            'password' => 'technical-test-password',
        ]);
        $row = $this->createRow();
        $service = app(TargetGroupReviewService::class);
        $service->markNeedsReview($row, 'NAME_CONFLICT');

        $approved = $service->decide($row->fresh(), TargetGroupReviewService::OUTCOME_APPROVED, 'NAME_CONFLICT', [
            'actor_user_id' => $actor->id,
            'operator_note' => 'Synthetic explicit review decision.',
            'correlation_id' => 'SYN-CORRELATION-APPROVE',
        ]);

        $this->assertSame('APPROVED', $approved->review_status);
        $this->assertSame('APPROVED', $approved->review_outcome);
        $this->assertSame($actor->id, $approved->reviewed_by);
        $this->assertNotNull($approved->reviewed_at);

        $this->expectException(LogicException::class);
        $service->decide($approved, TargetGroupReviewService::OUTCOME_APPROVED, 'NAME_CONFLICT', [
            'actor_user_id' => $actor->id,
        ]);
    }

    private function createRow(array $overrides = []): TargetGroupRow
    {
        $jobId = DB::table('target_group_jobs')->insertGetId([
            'group_name' => 'SYNTHETIC_REVIEW_GROUP',
            'status' => 'staged',
            'total_files' => 1,
            'total_rows' => 1,
            'valid_rows' => 0,
            'invalid_rows' => 1,
            'review_rows' => 0,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        $fileId = DB::table('target_group_files')->insertGetId([
            'target_group_job_id' => $jobId,
            'original_filename' => 'synthetic.csv',
            'stored_path' => 'synthetic/synthetic.csv',
            'mime_type' => 'text/csv',
            'size_bytes' => 1,
            'sha256' => hash('sha256', 'synthetic.csv'),
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return TargetGroupRow::query()->create(array_merge([
            'target_group_job_id' => $jobId,
            'target_group_file_id' => $fileId,
            'sheet_name' => 'SYNTHETIC',
            'row_number' => 1,
            'raw_payload' => ['source' => 'synthetic-test'],
            'raw_cid' => '1234567890121',
            'normalized_cid' => '1234567890121',
            'cid_status' => 'valid',
            'raw_full_name' => 'SYNTHETIC_NAME',
            'normalized_full_name' => 'SYNTHETIC_NAME',
            'raw_birth_date' => '2000-01-01',
            'normalized_birth_date' => '2000-01-01',
            'validation_status' => 'valid',
            'review_reason' => null,
        ], $overrides));
    }
}
