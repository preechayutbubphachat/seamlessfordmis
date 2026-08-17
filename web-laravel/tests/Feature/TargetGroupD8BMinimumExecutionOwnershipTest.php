<?php

namespace Tests\Feature;

use App\Models\TargetGroupImportRequest;
use App\Models\TargetGroupJob;
use App\Services\Import\TargetGroupCanonicalJobOwnershipService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use LogicException;
use Tests\TestCase;

final class TargetGroupD8BMinimumExecutionOwnershipTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        DB::table('users')->insert([
            'id' => 17,
            'name' => 'Synthetic D8-B Owner',
            'email' => 'synthetic-d8b-owner@example.test',
            'password' => password_hash('synthetic-test-only', PASSWORD_BCRYPT),
        ]);
    }

    public function test_d7_request_resolves_to_one_canonical_job_without_execution_side_effects(): void
    {
        $result = $this->service()->register($this->input());

        $this->assertSame('NOT_STARTED', $result['state']);
        $this->assertSame($this->input()['import_request_id'], $result['request']->getKey());
        $this->assertInstanceOf(TargetGroupJob::class, $result['job']);
        $this->assertSame($result['job']->getKey(), $result['request']->canonical_job_id);
        $this->assertSame($result['request']->getKey(), $result['job']->import_request_id);
        $this->assertSame('RECEIVED', $result['job']->status);
        $this->assertSame(1, TargetGroupImportRequest::query()->count());
        $this->assertSame(1, TargetGroupJob::query()->count());
        $this->assertSame(0, DB::table('target_group_job_attempts')->count());
        $this->assertSame(0, DB::table('target_group_file_versions')->count());
        $this->assertSame(0, DB::table('target_group_history_rows')->count());
    }

    public function test_same_request_and_same_context_replays_the_same_canonical_job(): void
    {
        $input = $this->input();
        $first = $this->service()->register($input);
        $second = $this->service()->register($input);

        $this->assertSame('NOT_STARTED', $second['state']);
        $this->assertSame($first['canonical_job_id'], $second['canonical_job_id']);
        $this->assertSame(1, TargetGroupJob::query()->count());
        $this->assertSame(1, TargetGroupImportRequest::query()->count());
    }

    public function test_conflicting_immutable_d7_context_fails_closed_without_mutating_owner(): void
    {
        $input = $this->input();
        $this->service()->register($input);

        try {
            $this->service()->register($this->input(['candidate_version_id' => 102]));
            $this->fail('Expected immutable context conflict.');
        } catch (LogicException $exception) {
            $this->assertSame('IDEMPOTENCY_KEY_CONTEXT_CONFLICT', $exception->getMessage());
        }

        $request = TargetGroupImportRequest::query()->sole();
        $this->assertSame('PENDING', $request->lifecycle_state);
        $this->assertSame(1, TargetGroupJob::query()->count());
    }

    public function test_in_progress_replay_returns_existing_owner_without_second_job(): void
    {
        $input = $this->input();
        $first = $this->service()->register($input);

        DB::table('import_requests')->where('import_request_id', $input['import_request_id'])->update(['lifecycle_state' => 'PROCESSING']);
        DB::table('target_group_jobs')->where('id', $first['canonical_job_id'])->update(['status' => 'PROCESSING']);

        $replay = $this->service()->register($input);

        $this->assertSame('IN_PROGRESS', $replay['state']);
        $this->assertSame($first['canonical_job_id'], $replay['canonical_job_id']);
        $this->assertSame(1, TargetGroupJob::query()->count());
    }

    public function test_failure_before_commit_replays_failure_without_d7_evidence(): void
    {
        $input = $this->input();
        $first = $this->service()->register($input);

        DB::table('import_requests')->where('import_request_id', $input['import_request_id'])->update([
            'lifecycle_state' => 'FAILED',
            'failure_code' => 'SYNTHETIC_VALIDATION_FAILED',
        ]);
        DB::table('target_group_jobs')->where('id', $first['canonical_job_id'])->update([
            'status' => 'FAILED_FINAL',
            'error_message' => 'synthetic failure before commit',
        ]);

        $replay = $this->service()->register($input);

        $this->assertSame('FAILED_BEFORE_COMMIT', $replay['state']);
        $this->assertSame('SYNTHETIC_VALIDATION_FAILED', $replay['reason']);
        $this->assertSame(0, DB::table('target_group_file_versions')->count());
        $this->assertSame(0, DB::table('target_group_version_supersessions')->count());
    }

    public function test_unknown_outcome_is_reconciliation_required_and_does_not_create_second_job(): void
    {
        $input = $this->input();
        $first = $this->service()->register($input);

        DB::table('import_requests')->where('import_request_id', $input['import_request_id'])->update([
            'lifecycle_state' => 'RECONCILIATION_REQUIRED',
            'reconciliation_state' => 'RECONCILIATION_REQUIRED',
            'reconciliation_reference' => 'synthetic-unknown',
        ]);
        DB::table('target_group_jobs')->where('id', $first['canonical_job_id'])->update(['status' => 'RECONCILIATION_REQUIRED']);

        $replay = $this->service()->register($input);

        $this->assertSame('OUTCOME_UNKNOWN', $replay['state']);
        $this->assertSame('RECONCILIATION_REQUIRED', $replay['reason']);
        $this->assertSame(1, TargetGroupJob::query()->count());
        $this->assertSame(0, DB::table('target_group_file_versions')->count());
    }

    public function test_binding_conflict_is_unknown_and_never_chooses_a_job_winner(): void
    {
        $input = $this->input();
        $first = $this->service()->register($input);
        $second = $this->service()->register($this->input([
            'import_request_id' => '44444444-4444-4444-8444-444444444444',
            'lineage_id' => '55555555-5555-4555-8555-555555555555',
            'candidate_version_id' => 201,
            'expected_predecessor_version_id' => 200,
        ]));

        DB::table('import_requests')->where('import_request_id', $input['import_request_id'])->update([
            'canonical_job_id' => $second['canonical_job_id'],
        ]);

        $replay = $this->service()->register($input);

        $this->assertSame('OUTCOME_UNKNOWN', $replay['state']);
        $this->assertSame('CANONICAL_JOB_BINDING_CONFLICT', $replay['reason']);
        $this->assertSame($second['canonical_job_id'], $replay['canonical_job_id']);
        $this->assertNotSame($first['canonical_job_id'], $replay['canonical_job_id']);
        $this->assertSame(2, TargetGroupJob::query()->count());
    }

    public function test_preexisting_d7_candidate_evidence_is_not_treated_as_committed(): void
    {
        $input = $this->input();
        $first = $this->service()->register($input);
        $this->seedCandidateEvidence($input, $first['canonical_job_id']);

        $replay = $this->service()->register($input);

        $this->assertSame('NOT_STARTED', $replay['state']);
        $this->assertSame(0, DB::table('target_group_version_supersessions')->count());
        $this->assertSame(0, DB::table('audit_logs')->where('action', 'VERSION_SUPERSEDED')->count());
    }

    public function test_committed_replay_requires_existing_d7_evidence_and_does_not_execute_activation(): void
    {
        $input = $this->input();
        $first = $this->service()->register($input);
        $evidence = $this->seedCommittedEvidence($input, $first['canonical_job_id']);

        $replay = $this->service()->register($input);

        $this->assertSame('COMMITTED', $replay['state']);
        $this->assertSame('AUTHORITATIVE_COMMITTED_REPLAY', $replay['result']['result']);
        $this->assertSame($evidence['candidate_id'], $replay['result']['successor_version_id']);
        $this->assertSame('ACTIVE', DB::table('target_group_file_versions')->where('id', $evidence['candidate_id'])->value('version_status'));
        $this->assertSame(1, DB::table('target_group_version_supersessions')->count());
        $this->assertSame(1, DB::table('audit_logs')->where('action', 'VERSION_SUPERSEDED')->count());
    }

    public function test_d7_context_fingerprint_is_canonical_and_d8a_request_behavior_remains_job_free(): void
    {
        $input = $this->input();
        $d7Request = (new \App\Services\Import\TargetGroupImportRequestIdempotencyService())->registerD7Activation($input);
        $this->assertSame($input['import_request_id'], $d7Request->getKey());
        $this->assertSame(0, DB::table('target_group_jobs')->count());

        $result = $this->service()->register($input);
        $preimage = "d8-context-v1\noperation=target_group_d7_activation\nscope_key=synthetic.d7.scope\ncontent_sha256={$input['content_sha256']}\nbyte_size=14\nlineage_id={$input['lineage_id']}\ncandidate_version_id=101\nexpected_predecessor_version_id=100\n";

        $this->assertSame(hash('sha256', $preimage), $result['request']->context_fingerprint);
        $this->assertSame(1, DB::table('target_group_jobs')->count());

        $d8aInput = [
            'import_request_id' => '66666666-6666-4666-8666-666666666666',
            'operation' => 'target_group_import',
            'scope_key' => 'synthetic.d8a.scope',
            'content_sha256' => hash('sha256', 'SYN_D8A_REQUEST'),
            'byte_size' => 15,
            'owner_user_id' => 17,
        ];
        (new \App\Services\Import\TargetGroupImportRequestIdempotencyService())->register($d8aInput);

        $this->assertSame(2, TargetGroupImportRequest::query()->count());
        $this->assertSame(1, DB::table('target_group_jobs')->count());
    }

    private function service(): TargetGroupCanonicalJobOwnershipService
    {
        return new TargetGroupCanonicalJobOwnershipService();
    }

    private function seedCandidateEvidence(array $input, int $jobId): void
    {
        $now = now();
        $fileId = DB::table('target_group_files')->insertGetId([
            'target_group_job_id' => $jobId,
            'original_filename' => 'synthetic-candidate.csv',
            'stored_path' => 'synthetic/candidate.csv',
            'mime_type' => 'text/csv',
            'size_bytes' => 14,
            'sha256' => $input['content_sha256'],
            'sheet_count' => null,
            'row_count' => 1,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('target_group_lineages')->insert([
            'lineage_id' => $input['lineage_id'],
            'next_version_number' => 3,
            'active_version_id' => null,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('target_group_file_versions')->insert([
            'id' => 100,
            'lineage_id' => $input['lineage_id'],
            'version_token' => '99999999-9999-4999-8999-999999999999',
            'version_number' => 1,
            'target_group_file_id' => $fileId,
            'target_group_job_id' => $jobId,
            'previous_version_id' => null,
            'superseded_by_id' => null,
            'version_status' => 'ACTIVE',
            'correlation_id' => $input['correlation_id'],
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('target_group_file_versions')->insert([
            'id' => 101,
            'lineage_id' => $input['lineage_id'],
            'version_token' => 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
            'version_number' => 2,
            'target_group_file_id' => $fileId,
            'target_group_job_id' => $jobId,
            'previous_version_id' => 100,
            'superseded_by_id' => null,
            'version_status' => 'CANDIDATE',
            'correction_reason' => 'synthetic-candidate',
            'correlation_id' => $input['correlation_id'],
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('target_group_lineages')->where('lineage_id', $input['lineage_id'])->update(['active_version_id' => 100]);
    }

    /**
     * @return array{file_id:int,predecessor_id:int,candidate_id:int}
     */
    private function seedCommittedEvidence(array $input, int $jobId): array
    {
        $now = now();
        $fileId = DB::table('target_group_files')->insertGetId([
            'target_group_job_id' => $jobId,
            'original_filename' => 'synthetic-correction.csv',
            'stored_path' => 'synthetic/correction.csv',
            'mime_type' => 'text/csv',
            'size_bytes' => 14,
            'sha256' => $input['content_sha256'],
            'sheet_count' => null,
            'row_count' => 1,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('target_group_lineages')->insert([
            'lineage_id' => $input['lineage_id'],
            'next_version_number' => 3,
            'active_version_id' => null,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        $predecessorId = 100;
        DB::table('target_group_file_versions')->insert([
            'id' => $predecessorId,
            'lineage_id' => $input['lineage_id'],
            'version_token' => '77777777-7777-4777-8777-777777777777',
            'version_number' => 1,
            'target_group_file_id' => $fileId,
            'target_group_job_id' => $jobId,
            'previous_version_id' => null,
            'superseded_by_id' => null,
            'version_status' => 'ACTIVE',
            'correction_reason' => null,
            'supersession_reason' => null,
            'superseded_at' => null,
            'superseded_by_user_id' => null,
            'confirmed_by_user_id' => null,
            'confirmed_at' => null,
            'correlation_id' => $input['correlation_id'],
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        $candidateId = 101;
        DB::table('target_group_file_versions')->insert([
            'id' => $candidateId,
            'lineage_id' => $input['lineage_id'],
            'version_token' => '88888888-8888-4888-8888-888888888888',
            'version_number' => 2,
            'target_group_file_id' => $fileId,
            'target_group_job_id' => $jobId,
            'previous_version_id' => $predecessorId,
            'superseded_by_id' => null,
            'version_status' => 'ACTIVE',
            'correction_reason' => 'synthetic-correction',
            'supersession_reason' => 'synthetic-correction',
            'superseded_at' => null,
            'superseded_by_user_id' => null,
            'confirmed_by_user_id' => null,
            'confirmed_at' => null,
            'correlation_id' => $input['correlation_id'],
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('target_group_file_versions')->where('id', $predecessorId)->update([
            'version_status' => 'SUPERSEDED',
            'superseded_by_id' => $candidateId,
            'superseded_at' => $now,
            'superseded_by_user_id' => 17,
            'supersession_reason' => 'synthetic-correction',
        ]);
        DB::table('target_group_lineages')->where('lineage_id', $input['lineage_id'])->update(['active_version_id' => $candidateId]);
        DB::table('target_group_version_supersessions')->insert([
            'predecessor_version_id' => $predecessorId,
            'successor_version_id' => $candidateId,
            'committed_by_user_id' => 17,
            'correlation_id' => $input['correlation_id'],
            'supersession_reason' => 'synthetic-correction',
            'committed_at' => $now,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('audit_logs')->insert([
            'actor_user_id' => 17,
            'action' => 'VERSION_SUPERSEDED',
            'entity_type' => 'target_group_file_version',
            'entity_id' => $candidateId,
            'before_payload' => json_encode(['active_version_id' => $predecessorId]),
            'after_payload' => json_encode(['active_version_id' => $candidateId]),
            'created_at' => $now,
            'correlation_id' => $input['correlation_id'],
            'target_group_job_id' => $jobId,
            'target_group_file_id' => $fileId,
            'lineage_id' => $input['lineage_id'],
            'version_id' => $candidateId,
            'predecessor_version_id' => $predecessorId,
            'successor_version_id' => $candidateId,
        ]);

        return ['file_id' => $fileId, 'predecessor_id' => $predecessorId, 'candidate_id' => $candidateId];
    }

    private function input(array $overrides = []): array
    {
        return array_merge([
            'import_request_id' => '11111111-1111-4111-8111-111111111111',
            'operation' => 'target_group_d7_activation',
            'scope_key' => 'synthetic.d7.scope',
            'content_sha256' => hash('sha256', 'SYN_D7_REQUEST'),
            'byte_size' => 14,
            'owner_user_id' => 17,
            'lineage_id' => '22222222-2222-4222-8222-222222222222',
            'candidate_version_id' => 101,
            'expected_predecessor_version_id' => 100,
            'correlation_id' => '33333333-3333-4333-8333-333333333333',
        ], $overrides);
    }
}
