<?php

namespace Tests\Feature;

use App\Models\AuditLog;
use App\Services\Import\TargetGroupCanonicalJobOwnershipService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use LogicException;
use Tests\TestCase;

final class TargetGroupD7ActivationD8BIntegrationTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        DB::table('users')->insert([
            'id' => 17,
            'name' => 'Synthetic D7 D8-B Owner',
            'email' => 'synthetic-d7-d8b-owner@example.test',
            'password' => password_hash('synthetic-test-only', PASSWORD_BCRYPT),
        ]);
    }

    public function test_corrected_success_runs_inside_one_d8_envelope_and_links_typed_audit(): void
    {
        $fixture = $this->ownedFixture();

        $result = $this->service()->activateD7($fixture['input']);

        $this->assertSame('COMPLETED', $result['state']);
        $this->assertSame('ACTIVATED', $result['result']['result']);
        $this->assertSame($fixture['candidate'], $result['result']['version']->getKey());
        $this->assertSame('COMPLETED', $result['request']->lifecycle_state);
        $this->assertNotNull($result['request']->completed_at);
        $this->assertSame('COMPLETED', $result['job']->status);
        $this->assertNotNull($result['job']->finished_at);
        $this->assertSame('SUPERSEDED', $this->value('target_group_file_versions', $fixture['predecessor'], 'version_status'));
        $this->assertSame('ACTIVE', $this->value('target_group_file_versions', $fixture['candidate'], 'version_status'));
        $this->assertSame($fixture['candidate'], $this->value('target_group_lineages', $fixture['lineage'], 'active_version_id', 'lineage_id'));
        $this->assertSame(1, DB::table('target_group_version_supersessions')->count());
        $this->assertSame(1, AuditLog::query()->where('action', 'VERSION_SUPERSEDED')->count());

        $audit = AuditLog::query()->where('action', 'VERSION_SUPERSEDED')->sole();
        $this->assertSame($fixture['input']['import_request_id'], $audit->import_request_id);
        $this->assertSame($fixture['jobId'], $audit->target_group_job_id);
        $this->assertSame($fixture['input']['correlation_id'], $audit->correlation_id);
        $this->assertSame($fixture['lineage'], $audit->lineage_id);
        $this->assertSame($fixture['predecessor'], $audit->predecessor_version_id);
        $this->assertSame($fixture['candidate'], $audit->successor_version_id);
        $this->assertSame(0, DB::table('target_group_job_attempts')->count());
        $this->assertSame(0, DB::table('target_group_history_rows')->count());
    }

    public function test_same_authoritative_request_replays_without_duplicate_activation_evidence(): void
    {
        $fixture = $this->ownedFixture();
        $first = $this->service()->activateD7($fixture['input']);
        $counts = $this->evidenceCounts($fixture['lineage']);

        $replay = $this->service()->activateD7($fixture['input']);

        $this->assertSame('COMMITTED', $replay['state']);
        $this->assertSame('AUTHORITATIVE_ALREADY_COMMITTED_REPLAY', $replay['result']['result']);
        $this->assertSame($first['result']['version']->getKey(), $replay['result']['version']->getKey());
        $this->assertSame($counts, $this->evidenceCounts($fixture['lineage']));
        $this->assertSame(1, DB::table('target_group_jobs')->count());
        $this->assertSame(1, DB::table('import_requests')->count());
    }

    public function test_root_activation_is_rejected_and_known_failure_persists_without_d7_mutation(): void
    {
        $fixture = $this->ownedFixture();
        DB::table('target_group_lineages')->where('lineage_id', $fixture['lineage'])->update(['active_version_id' => null]);

        $result = $this->service()->activateD7($fixture['input']);

        $this->assertSame('FAILED_BEFORE_COMMIT', $result['state']);
        $this->assertSame('ROOT_ACTIVATION_NOT_AUTHORIZED', $result['reason']);
        $this->assertSame('FAILED', $result['request']->lifecycle_state);
        $this->assertSame('ROOT_ACTIVATION_NOT_AUTHORIZED', $result['request']->failure_code);
        $this->assertSame('FAILED_FINAL', $result['job']->status);
        $this->assertSame('ROOT_ACTIVATION_NOT_AUTHORIZED', $result['job']->error_message);
        $this->assertSame('ACTIVE', $this->value('target_group_file_versions', $fixture['predecessor'], 'version_status'));
        $this->assertSame('CANDIDATE', $this->value('target_group_file_versions', $fixture['candidate'], 'version_status'));
        $this->assertNull($this->value('target_group_lineages', $fixture['lineage'], 'active_version_id', 'lineage_id'));
        $this->assertSame(0, DB::table('target_group_version_supersessions')->count());
        $this->assertSame(0, AuditLog::query()->where('action', 'VERSION_SUPERSEDED')->count());
    }

    public function test_candidate_job_mismatch_fails_closed_without_pointer_or_supersession_mutation(): void
    {
        $fixture = $this->ownedFixture(candidateJobId: null, mismatchCandidateJob: true);

        $result = $this->service()->activateD7($fixture['input']);

        $this->assertSame('FAILED_BEFORE_COMMIT', $result['state']);
        $this->assertSame('CANDIDATE_CANONICAL_JOB_MISMATCH', $result['reason']);
        $this->assertSame('ACTIVE', $this->value('target_group_file_versions', $fixture['predecessor'], 'version_status'));
        $this->assertSame('CANDIDATE', $this->value('target_group_file_versions', $fixture['candidate'], 'version_status'));
        $this->assertSame($fixture['predecessor'], $this->value('target_group_lineages', $fixture['lineage'], 'active_version_id', 'lineage_id'));
        $this->assertSame(0, DB::table('target_group_version_supersessions')->count());
        $this->assertSame(0, AuditLog::query()->where('action', 'VERSION_SUPERSEDED')->count());
    }

    public function test_immutable_context_conflict_fails_closed_without_changing_request_or_job(): void
    {
        $fixture = $this->ownedFixture();
        $conflicting = $fixture['input'];
        $conflicting['candidate_version_id'] = $fixture['candidate'] + 1000;

        try {
            $this->service()->activateD7($conflicting);
            $this->fail('Expected immutable D7 context conflict.');
        } catch (LogicException $exception) {
            $this->assertSame('IDEMPOTENCY_KEY_CONTEXT_CONFLICT', $exception->getMessage());
        }

        $request = DB::table('import_requests')->where('import_request_id', $fixture['input']['import_request_id'])->first();
        $job = DB::table('target_group_jobs')->where('id', $fixture['jobId'])->first();
        $this->assertSame('PENDING', $request->lifecycle_state);
        $this->assertSame('RECEIVED', $job->status);
        $this->assertSame(0, DB::table('target_group_version_supersessions')->count());
        $this->assertSame(0, AuditLog::query()->where('action', 'VERSION_SUPERSEDED')->count());
    }

    public function test_unknown_outcome_is_reconciliation_required_and_never_reruns_d7(): void
    {
        $fixture = $this->ownedFixture();
        DB::table('import_requests')->where('import_request_id', $fixture['input']['import_request_id'])->update([
            'lifecycle_state' => 'OUTCOME_UNKNOWN',
            'reconciliation_state' => 'RECONCILIATION_REQUIRED',
            'reconciliation_reference' => 'synthetic-unknown',
        ]);
        DB::table('target_group_jobs')->where('id', $fixture['jobId'])->update([
            'status' => 'RECONCILIATION_REQUIRED',
            'error_message' => 'RECONCILIATION_REQUIRED',
        ]);

        $result = $this->service()->activateD7($fixture['input']);

        $this->assertSame('OUTCOME_UNKNOWN', $result['state']);
        $this->assertSame('RECONCILIATION_REQUIRED', $result['reason']);
        $this->assertSame('OUTCOME_UNKNOWN', $result['request']->lifecycle_state);
        $this->assertSame('RECONCILIATION_REQUIRED', $result['job']->status);
        $this->assertSame(0, DB::table('target_group_version_supersessions')->count());
        $this->assertSame(0, AuditLog::query()->where('action', 'VERSION_SUPERSEDED')->count());
    }

    private function service(): TargetGroupCanonicalJobOwnershipService
    {
        return new TargetGroupCanonicalJobOwnershipService();
    }

    private function ownedFixture(?int $candidateJobId = null, bool $mismatchCandidateJob = false): array
    {
        $input = $this->input();
        $registered = $this->service()->register($input);
        $jobId = (int) $registered['canonical_job_id'];
        $lineage = $input['lineage_id'];
        $otherJobId = null;
        if ($mismatchCandidateJob) {
            $otherJobId = (int) DB::table('target_group_jobs')->insertGetId([
                'group_name' => 'SYN_OTHER',
                'status' => 'PREVIEW',
            ]);
        }
        DB::table('target_group_lineages')->insert([
            'lineage_id' => $lineage,
            'next_version_number' => 3,
            'active_version_id' => null,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        $preFile = $this->createFile($jobId, 'predecessor.csv', 'SYN_PREDECESSOR');
        $candidateFile = $this->createFile($jobId, 'candidate.csv', 'SYN_CANDIDATE');
        $predecessor = $this->createVersion($lineage, $jobId, $preFile, 'ACTIVE', 1, null);
        $candidateJob = $mismatchCandidateJob ? $otherJobId : ($candidateJobId ?? $jobId);
        $candidate = $this->createVersion($lineage, $candidateJob, $candidateFile, 'CANDIDATE', 2, $predecessor);
        DB::table('target_group_lineages')->where('lineage_id', $lineage)->update(['active_version_id' => $predecessor]);

        return [
            'input' => array_merge($input, ['lineage_id' => $lineage, 'candidate_version_id' => $candidate, 'expected_predecessor_version_id' => $predecessor]),
            'jobId' => $jobId,
            'lineage' => $lineage,
            'predecessor' => $predecessor,
            'candidate' => $candidate,
        ];
    }

    private function input(): array
    {
        return [
            'import_request_id' => '11111111-1111-4111-8111-111111111111',
            'operation' => 'target_group_d7_activation',
            'scope_key' => 'synthetic.d7.integration',
            'content_sha256' => hash('sha256', 'SYN_D7_INTEGRATION'),
            'byte_size' => 18,
            'owner_user_id' => 17,
            'lineage_id' => (string) Str::uuid(),
            'candidate_version_id' => 2,
            'expected_predecessor_version_id' => 1,
            'correlation_id' => '33333333-3333-4333-8333-333333333333',
        ];
    }

    private function createFile(int $jobId, string $filename, string $bytes): int
    {
        return (int) DB::table('target_group_files')->insertGetId([
            'target_group_job_id' => $jobId,
            'original_filename' => $filename,
            'stored_path' => 'synthetic/'.$filename,
            'mime_type' => 'text/csv',
            'size_bytes' => strlen($bytes),
            'sha256' => hash('sha256', $bytes),
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function createVersion(string $lineage, int $jobId, int $fileId, string $status, int $number, ?int $previous): int
    {
        return (int) DB::table('target_group_file_versions')->insertGetId([
            'id' => $number,
            'lineage_id' => $lineage,
            'version_token' => (string) Str::uuid(),
            'version_number' => $number,
            'target_group_file_id' => $fileId,
            'target_group_job_id' => $jobId,
            'previous_version_id' => $previous,
            'version_status' => $status,
            'correction_reason' => $status === 'CANDIDATE' ? 'SYN_CORRECTION' : null,
            'correlation_id' => (string) Str::uuid(),
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function evidenceCounts(string $lineage): array
    {
        return [
            DB::table('target_group_version_supersessions')->count(),
            AuditLog::query()->where('action', 'VERSION_SUPERSEDED')->count(),
            DB::table('target_group_lineages')->where('lineage_id', $lineage)->value('active_version_id'),
        ];
    }

    private function value(string $table, int|string $key, string $column, string $keyColumn = 'id'): mixed
    {
        return DB::table($table)->where($keyColumn, $key)->value($column);
    }
}
