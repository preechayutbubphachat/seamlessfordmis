<?php

namespace Tests\Feature;

use App\Models\AuditLog;
use App\Services\Import\TargetGroupFileVersionActivationService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use LogicException;
use Tests\TestCase;

final class TargetGroupD7ActivationSupersessionTest extends TestCase
{
    use RefreshDatabase;

    public function test_valid_activation_transitions_state_pointer_relation_and_one_safe_audit(): void
    {
        $f = $this->fixture();
        $beforeCounts = $this->d8Counts();
        $result = $this->service()->activate($this->input($f));
        $this->assertSame('ACTIVATED', $result['result']);
        $this->assertSame($f['candidate'], $result['version']->getKey());
        $this->assertSame('SUPERSEDED', $this->value('target_group_file_versions', $f['predecessor'], 'version_status'));
        $this->assertSame('ACTIVE', $this->value('target_group_file_versions', $f['candidate'], 'version_status'));
        $this->assertSame($f['candidate'], $this->value('target_group_lineages', $f['lineage'], 'active_version_id', 'lineage_id'));
        $this->assertSame(1, DB::table('target_group_version_supersessions')->count());
        $supersession = DB::table('target_group_version_supersessions')->first();
        $this->assertSame($f['predecessor'], $supersession->predecessor_version_id);
        $this->assertSame($f['candidate'], $supersession->successor_version_id);
        $this->assertSame($f['reason'], $supersession->supersession_reason);
        $audit = AuditLog::query()->where('action', 'VERSION_SUPERSEDED')->sole();
        $this->assertSame($f['candidate'], $audit->entity_id);
        $this->assertSame($f['user'], $audit->actor_user_id);
        $this->assertSame($f['lineage'], $audit->lineage_id);
        $this->assertSame($f['job'], $audit->target_group_job_id);
        $this->assertSame($f['file'], $audit->target_group_file_id);
        $this->assertSame($f['predecessor'], $audit->predecessor_version_id);
        $this->assertSame($f['candidate'], $audit->successor_version_id);
        $this->assertSame($f['correlation'], $audit->correlation_id);
        $this->assertSame('ACTIVE', $audit->before_payload['predecessor_version_status']);
        $this->assertSame('CANDIDATE', $audit->before_payload['successor_version_status']);
        $this->assertSame('SUPERSEDED', $audit->after_payload['predecessor_version_status']);
        $this->assertSame('ACTIVE', $audit->after_payload['successor_version_status']);
        foreach (['raw_cid', 'patient', 'raw_patient_payload'] as $key) {
            $this->assertArrayNotHasKey($key, $audit->before_payload);
            $this->assertArrayNotHasKey($key, $audit->after_payload);
        }
        foreach (['raw_cid', 'patient', 'raw_patient_payload'] as $key) {
            $this->assertArrayNotHasKey($key, $audit->before_payload);
            $this->assertArrayNotHasKey($key, $audit->after_payload);
        }
        $this->assertSame($beforeCounts, $this->d8Counts());
        $this->assertSame(0, DB::table('target_group_history_rows')->count());
    }

    public function test_valid_confirmation_and_valid_candidate_rows_are_accepted(): void
    {
        $f = $this->fixture();
        $this->createRow($f, 'VALID');

        $this->assertSame('ACTIVATED', $this->service()->activate($this->input($f))['result']);
    }

    public function test_complete_approved_candidate_rows_are_accepted(): void
    {
        $f = $this->fixture();
        $this->createRow($f, 'APPROVED', 'APPROVED', $f['user']);

        $this->assertSame('ACTIVATED', $this->service()->activate($this->input($f))['result']);
    }

    public function test_missing_successor_confirmation_fails_before_any_d7_mutation(): void
    {
        foreach (['confirmed_by_user_id' => null, 'confirmed_at' => null] as $field => $value) {
            $f = $this->fixture();
            DB::table('target_group_file_versions')->where('id', $f['candidate'])->update([$field => $value]);

            $this->throws('MISSING_SUCCESSOR_CONFIRMATION', fn () => $this->service()->activate($this->input($f)));
            $this->assertActivationUnchanged($f);
        }
    }

    public function test_unacceptable_candidate_review_states_fail_closed_before_any_d7_mutation(): void
    {
        foreach (['PENDING_VALIDATION', 'NEEDS_REVIEW', 'REJECTED', 'UNRECOGNIZED'] as $status) {
            $f = $this->fixture();
            $this->createRow($f, $status);

            $this->throws('SUCCESSOR_REVIEW_NOT_ACCEPTABLE', fn () => $this->service()->activate($this->input($f)));
            $this->assertActivationUnchanged($f);
        }
    }

    public function test_approved_candidate_row_without_complete_approval_evidence_fails_closed(): void
    {
        $f = $this->fixture();
        $this->createRow($f, 'APPROVED');

        $this->throws('SUCCESSOR_REVIEW_NOT_ACCEPTABLE', fn () => $this->service()->activate($this->input($f)));
        $this->assertActivationUnchanged($f);
    }

    public function test_fresh_candidate_predecessor_lineage_and_root_rules_fail_closed(): void
    {
        $f = $this->fixture();
        $this->throws('PREDECESSOR_NOT_FOUND', fn () => $this->service()->activate($this->input($f, 999999, $f['candidate'])));
        $f = $this->fixture();
        $this->throws('CANDIDATE_NOT_FOUND', fn () => $this->service()->activate($this->input($f, $f['predecessor'], 999999)));
        $f = $this->fixture();
        DB::table('target_group_file_versions')->where('id', $f['candidate'])->update(['previous_version_id' => $f['other_version']]);
        $this->throws('CANDIDATE_PREDECESSOR_MISMATCH', fn () => $this->service()->activate($this->input($f)));
        $f = $this->fixture();
        DB::table('target_group_file_versions')->where('id', $f['candidate'])->update(['lineage_id' => $f['foreign_lineage']]);
        $this->throws('CANDIDATE_LINEAGE_MISMATCH', fn () => $this->service()->activate($this->input($f)));
        $f = $this->fixture();
        DB::table('target_group_lineages')->where('lineage_id', $f['lineage'])->update(['active_version_id' => null]);
        $this->throws('ROOT_ACTIVATION_NOT_AUTHORIZED', fn () => $this->service()->activate($this->input($f)));
    }

    public function test_status_pointer_multiple_active_and_existing_relation_corruption_fail_closed(): void
    {
        $f = $this->fixture();
        DB::table('target_group_file_versions')->where('id', $f['candidate'])->update(['version_status' => 'REJECTED']);
        $this->throws('CANDIDATE_NOT_ELIGIBLE', fn () => $this->service()->activate($this->input($f)));
        $f = $this->fixture();
        DB::table('target_group_lineages')->where('lineage_id', $f['lineage'])->update(['active_version_id' => $f['candidate']]);
        $this->throws('CORRUPT_ACTIVE_STATE', fn () => $this->service()->activate($this->input($f)));
        $f = $this->fixture();
        $this->createVersion($f['lineage'], $f['other_job'], $f['other_file'], 'ACTIVE', 4, null);
        $this->throws('CORRUPT_ACTIVE_STATE', fn () => $this->service()->activate($this->input($f)));
        $f = $this->fixture();
        $other = $f['other_version'];
        DB::table('target_group_version_supersessions')->insert(['predecessor_version_id' => $f['predecessor'], 'successor_version_id' => $other, 'committed_by_user_id' => $f['user'], 'correlation_id' => (string) Str::uuid(), 'supersession_reason' => 'SYN_OTHER', 'committed_at' => now(), 'created_at' => now(), 'updated_at' => now()]);
        $this->throws('CORRUPT_ACTIVE_STATE', fn () => $this->service()->activate($this->input($f)));
    }

    public function test_cross_lineage_predecessor_and_stale_predecessor_fail_closed(): void
    {
        $f = $this->fixture();
        DB::table('target_group_lineages')->where('lineage_id', $f['lineage'])->update(['active_version_id' => $f['foreign_version']]);
        $this->throws('PREDECESSOR_LINEAGE_MISMATCH', fn () => $this->service()->activate($this->input($f, $f['foreign_version'])));
        $f = $this->fixture();
        $this->service()->activate($this->input($f));
        $stale = $this->createVersion($f['lineage'], $f['other_job'], $f['other_file'], 'CANDIDATE', 4, $f['predecessor']);
        $this->throws('CORRUPT_ACTIVE_STATE', fn () => $this->service()->activate($this->input($f, $f['predecessor'], $stale)));
    }

    public function test_exact_committed_replay_has_no_second_business_mutation(): void
    {
        $f = $this->fixture();
        $first = $this->service()->activate($this->input($f));
        $before = [DB::table('target_group_version_supersessions')->count(), AuditLog::query()->where('action', 'VERSION_SUPERSEDED')->count(), $this->value('target_group_lineages', $f['lineage'], 'active_version_id', 'lineage_id')];
        $replayInput = $this->input($f);
        $replayInput['correlation_id'] = (string) Str::uuid();
        $replay = $this->service()->activate($replayInput);
        $this->assertSame('AUTHORITATIVE_ALREADY_COMMITTED_REPLAY', $replay['result']);
        $this->assertSame($first['version']->getKey(), $replay['version']->getKey());
        $this->assertSame($before, [DB::table('target_group_version_supersessions')->count(), AuditLog::query()->where('action', 'VERSION_SUPERSEDED')->count(), $this->value('target_group_lineages', $f['lineage'], 'active_version_id', 'lineage_id')]);
    }

    public function test_sequential_contenders_have_one_winner_and_no_second_relation_or_audit(): void
    {
        $f = $this->fixture();
        $second = $this->createVersion($f['lineage'], $f['other_job'], $f['other_file'], 'CANDIDATE', 4, $f['predecessor']);
        $this->assertSame('ACTIVATED', $this->service()->activate($this->input($f))['result']);
        $this->throws('CORRUPT_ACTIVE_STATE', fn () => $this->service()->activate($this->input($f, $f['predecessor'], $second)));
        $this->assertSame($f['candidate'], $this->value('target_group_lineages', $f['lineage'], 'active_version_id', 'lineage_id'));
        $this->assertSame(1, DB::table('target_group_version_supersessions')->count());
        $this->assertSame(1, AuditLog::query()->where('action', 'VERSION_SUPERSEDED')->count());
    }

    public function test_audit_failure_rolls_back_every_business_mutation(): void
    {
        $f = $this->fixture();
        AuditLog::creating(function (): void { throw new LogicException('SYN_ACTIVATION_AUDIT_FAILURE'); });
        try {
            $this->throws('SYN_ACTIVATION_AUDIT_FAILURE', fn () => $this->service()->activate($this->input($f)));
        } finally {
            AuditLog::flushEventListeners();
        }
        $this->assertSame('ACTIVE', $this->value('target_group_file_versions', $f['predecessor'], 'version_status'));
        $this->assertSame('CANDIDATE', $this->value('target_group_file_versions', $f['candidate'], 'version_status'));
        $this->assertSame($f['predecessor'], $this->value('target_group_lineages', $f['lineage'], 'active_version_id', 'lineage_id'));
        $this->assertSame(0, DB::table('target_group_version_supersessions')->count());
        $this->assertSame(0, AuditLog::query()->where('action', 'VERSION_SUPERSEDED')->count());
    }

    public function test_rows_reviews_files_and_d8_tables_are_preserved_and_history_is_absent(): void
    {
        $f = $this->fixture();
        DB::table('target_group_rows')->insert(['target_group_job_id' => $f['job'], 'target_group_file_id' => $f['file'], 'sheet_name' => 'Sheet1', 'row_number' => 1, 'raw_payload' => json_encode(['synthetic' => true]), 'cid_status' => 'NOT_EVALUATED', 'validation_status' => 'PENDING', 'review_status' => 'VALID']);
        $row = (int) DB::table('target_group_rows')->where('target_group_file_id', $f['file'])->value('id');
        DB::table('target_group_row_reviews')->insert(['target_group_job_id' => $f['job'], 'target_group_file_id' => $f['file'], 'target_group_row_id' => $row, 'correlation_id' => (string) Str::uuid(), 'from_status' => 'PENDING_VALIDATION', 'to_status' => 'VALID', 'created_at' => now()]);
        $beforeFile = DB::table('target_group_files')->where('id', $f['file'])->first();
        $beforeRows = DB::table('target_group_rows')->get()->all();
        $beforeReviews = DB::table('target_group_row_reviews')->get()->all();
        $beforeD8 = $this->d8Counts();
        $this->service()->activate($this->input($f));
        $this->assertEquals($beforeFile, DB::table('target_group_files')->where('id', $f['file'])->first());
        $this->assertEquals($beforeRows, DB::table('target_group_rows')->get()->all());
        $this->assertEquals($beforeReviews, DB::table('target_group_row_reviews')->get()->all());
        $this->assertSame($beforeD8, $this->d8Counts());
        $this->assertSame(0, DB::table('target_group_history_rows')->count());
    }

    private function service(): TargetGroupFileVersionActivationService { return new TargetGroupFileVersionActivationService(); }
    private function input(array $f, ?int $predecessor = null, ?int $candidate = null): array { return ['lineage_id' => $f['lineage'], 'candidate_version_id' => $candidate ?? $f['candidate'], 'expected_predecessor_version_id' => $predecessor ?? $f['predecessor'], 'actor_user_id' => $f['user'], 'correlation_id' => $f['correlation']]; }
    private function throws(string $code, callable $operation): void { try { $operation(); $this->fail("Expected {$code}."); } catch (LogicException $exception) { $this->assertSame($code, $exception->getMessage()); } }
    private function value(string $table, int|string $key, string $column, string $keyColumn = 'id'): mixed { return DB::table($table)->where($keyColumn, $key)->value($column); }
    private function d8Counts(): array { return [DB::table('import_requests')->count(), DB::table('target_group_jobs')->count(), DB::table('target_group_job_attempts')->count()]; }
    private function createUser(): int { return (int) DB::table('users')->insertGetId(['name' => 'Synthetic Operator', 'email' => 'operator-'.Str::uuid().'@example.test', 'password' => password_hash('synthetic-test-only', PASSWORD_BCRYPT)]); }
    private function createJob(string $name): int { return (int) DB::table('target_group_jobs')->insertGetId(['group_name' => $name, 'status' => 'PREVIEW']); }
    private function createFile(int $job, string $filename, string $bytes): int { return (int) DB::table('target_group_files')->insertGetId(['target_group_job_id' => $job, 'original_filename' => $filename, 'stored_path' => 'synthetic/'.$filename, 'mime_type' => 'text/csv', 'size_bytes' => strlen($bytes), 'sha256' => hash('sha256', $bytes)]); }
    private function createRow(array $f, ?string $status, ?string $outcome = null, ?int $reviewedBy = null): int { return (int) DB::table('target_group_rows')->insertGetId(['target_group_job_id' => $f['job'], 'target_group_file_id' => $f['file'], 'sheet_name' => 'Sheet1', 'row_number' => random_int(1, 1000000), 'raw_payload' => json_encode(['synthetic' => true]), 'cid_status' => 'NOT_EVALUATED', 'validation_status' => 'PENDING', 'review_status' => $status, 'review_outcome' => $outcome, 'reviewed_by' => $reviewedBy, 'reviewed_at' => $reviewedBy === null ? null : now()]); }
    private function assertActivationUnchanged(array $f): void { $this->assertSame('ACTIVE', $this->value('target_group_file_versions', $f['predecessor'], 'version_status')); $this->assertSame('CANDIDATE', $this->value('target_group_file_versions', $f['candidate'], 'version_status')); $this->assertSame($f['predecessor'], $this->value('target_group_lineages', $f['lineage'], 'active_version_id', 'lineage_id')); $this->assertSame(0, DB::table('target_group_version_supersessions')->count()); $this->assertSame(0, AuditLog::query()->where('action', 'VERSION_SUPERSEDED')->count()); }
    private function createVersion(string $lineage, int $job, int $file, string $status, int $number, ?int $previous): int { return (int) DB::table('target_group_file_versions')->insertGetId(['lineage_id' => $lineage, 'version_token' => (string) Str::uuid(), 'version_number' => $number, 'target_group_file_id' => $file, 'target_group_job_id' => $job, 'previous_version_id' => $previous, 'version_status' => $status, 'correction_reason' => $status === 'CANDIDATE' ? 'SYN_CORRECTION' : null, 'correlation_id' => (string) Str::uuid()]); }
    private function fixture(): array
    {
        $user = $this->createUser(); $lineage = (string) Str::uuid(); $foreignLineage = (string) Str::uuid();
        DB::table('target_group_lineages')->insert(['lineage_id' => $lineage, 'next_version_number' => 4, 'active_version_id' => null]);
        DB::table('target_group_lineages')->insert(['lineage_id' => $foreignLineage]);
        $preJob = $this->createJob('SYN_PRE'); $preFile = $this->createFile($preJob, 'pre.csv', 'SYN_PRE'); $predecessor = $this->createVersion($lineage, $preJob, $preFile, 'ACTIVE', 1, null);
        DB::table('target_group_lineages')->where('lineage_id', $lineage)->update(['active_version_id' => $predecessor]);
        $job = $this->createJob('SYN_CANDIDATE'); $file = $this->createFile($job, 'candidate.csv', 'SYN_CANDIDATE'); $candidate = $this->createVersion($lineage, $job, $file, 'CANDIDATE', 2, $predecessor); DB::table('target_group_file_versions')->where('id', $candidate)->update(['confirmed_by_user_id' => $user, 'confirmed_at' => now()]);
        $otherJob = $this->createJob('SYN_OTHER'); $otherFile = $this->createFile($otherJob, 'other.csv', 'SYN_OTHER'); $other = $this->createVersion($lineage, $otherJob, $otherFile, 'CANDIDATE', 3, null);
        $foreignJob = $this->createJob('SYN_FOREIGN'); $foreignFile = $this->createFile($foreignJob, 'foreign.csv', 'SYN_FOREIGN'); $foreign = $this->createVersion($foreignLineage, $foreignJob, $foreignFile, 'ACTIVE', 1, null);
        return ['user' => $user, 'lineage' => $lineage, 'foreign_lineage' => $foreignLineage, 'predecessor' => $predecessor, 'candidate' => $candidate, 'job' => $job, 'file' => $file, 'other_job' => $otherJob, 'other_file' => $otherFile, 'other_version' => $other, 'foreign_version' => $foreign, 'reason' => 'SYN_CORRECTION', 'correlation' => (string) Str::uuid()];
    }
}
