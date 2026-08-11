<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;
use Illuminate\Database\QueryException;
use Tests\TestCase;

final class TargetGroupD7D8SchemaFoundationTest extends TestCase
{
    use RefreshDatabase;

    public function test_six_foundation_tables_exist_with_structural_columns(): void
    {
        foreach ([
            'import_content_objects',
            'import_requests',
            'target_group_job_attempts',
            'target_group_lineages',
            'target_group_file_versions',
            'target_group_version_supersessions',
        ] as $table) {
            $this->assertTrue(Schema::hasTable($table));
        }

        $this->assertTrue(Schema::hasColumn('target_group_files', 'content_object_id'));
        $this->assertTrue(Schema::hasColumn('target_group_jobs', 'import_request_id'));
        $this->assertTrue(Schema::hasColumn('target_group_jobs', 'retry_of_job_id'));
        $this->assertTrue(Schema::hasColumn('audit_logs', 'version_token'));
    }

    public function test_duplicate_content_sha_is_rejected(): void
    {
        $sha = hash('sha256', 'SYN_CONTENT_A');
        DB::table('import_content_objects')->insert(['sha256' => $sha, 'byte_size' => 12]);

        $this->assertQueryException(fn () => DB::table('import_content_objects')->insert(['sha256' => $sha, 'byte_size' => 12]));
    }

    public function test_same_content_can_be_attached_once_per_job_context(): void
    {
        $contentId = DB::table('import_content_objects')->insertGetId(['sha256' => hash('sha256', 'SYN_SHARED'), 'byte_size' => 10]);
        $jobA = $this->insertJob('SYN_GROUP_A');
        $jobB = $this->insertJob('SYN_GROUP_B');

        $this->insertFile($jobA, $contentId, 'SYN_A.csv');
        $this->insertFile($jobB, $contentId, 'SYN_B.csv');
        $this->assertSame(2, DB::table('target_group_files')->count());

        $this->assertQueryException(fn () => $this->insertFile($jobA, $contentId, 'SYN_A_DUP.csv'));
    }

    public function test_duplicate_request_identity_is_rejected(): void
    {
        $requestId = (string) Str::uuid();
        $this->insertRequest($requestId, 'SYN_IMPORT');

        $this->assertQueryException(fn () => $this->insertRequest($requestId, 'SYN_IMPORT'));
    }

    public function test_one_canonical_job_is_bound_to_one_request(): void
    {
        $requestId = (string) Str::uuid();
        $this->insertRequest($requestId, 'SYN_IMPORT');
        $this->insertJob('SYN_CANONICAL', $requestId);

        $this->assertQueryException(fn () => $this->insertJob('SYN_DUPLICATE', $requestId));
    }

    public function test_manual_retry_preserves_prior_job_relation(): void
    {
        $first = $this->insertJob('SYN_FIRST');
        $retry = $this->insertJob('SYN_RETRY', null, $first);

        $this->assertSame($first, DB::table('target_group_jobs')->where('id', $retry)->value('retry_of_job_id'));
    }

    public function test_attempt_number_is_unique_and_recovery_metadata_is_structural(): void
    {
        $job = $this->insertJob('SYN_ATTEMPT');
        $attempt = (string) Str::uuid();
        DB::table('target_group_job_attempts')->insert([
            'attempt_id' => $attempt,
            'job_id' => $job,
            'attempt_number' => 1,
            'state' => 'RECONCILIATION_REQUIRED',
            'worker_token' => 'SYN_WORKER_TOKEN',
            'failure_code' => 'SYN_UNKNOWN_OUTCOME',
            'retryable' => false,
            'reconciliation_state' => 'REQUIRED',
            'reconciliation_reference' => 'SYN_EVIDENCE_REF',
            'correlation_id' => (string) Str::uuid(),
        ]);

        $this->assertSame('RECONCILIATION_REQUIRED', DB::table('target_group_job_attempts')->where('attempt_id', $attempt)->value('state'));
        $this->assertQueryException(fn () => DB::table('target_group_job_attempts')->insert([
            'attempt_id' => (string) Str::uuid(), 'job_id' => $job, 'attempt_number' => 1,
            'state' => 'STARTED', 'correlation_id' => (string) Str::uuid(),
        ]));
    }

    public function test_lineage_counter_starts_at_one(): void
    {
        $lineage = (string) Str::uuid();
        DB::table('target_group_lineages')->insert(['lineage_id' => $lineage]);
        $this->assertSame(1, DB::table('target_group_lineages')->where('lineage_id', $lineage)->value('next_version_number'));
    }

    public function test_version_token_is_unique(): void
    {
        [$lineage, $job, $file] = $this->versionPrerequisites('SYN_TOKEN');
        $token = (string) Str::uuid();
        $this->insertVersion($lineage, $job, $file, $token, 1);
        $this->assertQueryException(fn () => $this->insertVersion($lineage, $job, $file, $token, 2));
    }

    public function test_lineage_version_number_is_unique(): void
    {
        [$lineage, $job, $file] = $this->versionPrerequisites('SYN_NUMBER');
        $this->insertVersion($lineage, $job, $file, (string) Str::uuid(), 1);
        $this->assertQueryException(fn () => $this->insertVersion($lineage, $job, $file, (string) Str::uuid(), 1));
    }

    public function test_self_predecessor_is_rejected(): void
    {
        [$lineage, $job, $file] = $this->versionPrerequisites('SYN_SELF');
        $id = 701;
        $this->assertQueryException(fn () => DB::table('target_group_file_versions')->insert([
            'id' => $id, 'lineage_id' => $lineage, 'version_token' => (string) Str::uuid(), 'version_number' => 1,
            'target_group_file_id' => $file, 'target_group_job_id' => $job, 'previous_version_id' => $id,
            'version_status' => 'CANDIDATE', 'correlation_id' => (string) Str::uuid(),
        ]));
    }

    public function test_lineage_active_pointer_rejects_missing_version(): void
    {
        $lineage = (string) Str::uuid();
        DB::table('target_group_lineages')->insert(['lineage_id' => $lineage]);
        $this->assertQueryException(fn () => DB::table('target_group_lineages')->where('lineage_id', $lineage)->update(['active_version_id' => 999999]));
    }

    public function test_supersession_predecessor_and_successor_are_unique(): void
    {
        [$lineage, $job, $file] = $this->versionPrerequisites('SYN_SUPERSESSION');
        $first = $this->insertVersion($lineage, $job, $file, (string) Str::uuid(), 1);
        $second = $this->insertVersion($lineage, $job, $file, (string) Str::uuid(), 2, $first);
        DB::table('target_group_version_supersessions')->insert([
            'predecessor_version_id' => $first, 'successor_version_id' => $second,
            'correlation_id' => (string) Str::uuid(), 'supersession_reason' => 'SYN_CORRECTION',
        ]);
        $this->assertQueryException(fn () => DB::table('target_group_version_supersessions')->insert([
            'predecessor_version_id' => $first, 'successor_version_id' => $second,
            'correlation_id' => (string) Str::uuid(), 'supersession_reason' => 'SYN_DUPLICATE',
        ]));
    }

    public function test_audit_typed_references_accept_synthetic_foundation_identity(): void
    {
        $requestId = (string) Str::uuid();
        $this->insertRequest($requestId, 'SYN_AUDIT');
        $job = $this->insertJob('SYN_AUDIT_JOB', $requestId);
        $contentId = DB::table('import_content_objects')->insertGetId(['sha256' => hash('sha256', 'SYN_AUDIT_CONTENT'), 'byte_size' => 9]);
        $attemptId = (string) Str::uuid();
        DB::table('target_group_job_attempts')->insert([
            'attempt_id' => $attemptId, 'job_id' => $job, 'attempt_number' => 1, 'state' => 'STARTED',
            'correlation_id' => (string) Str::uuid(),
        ]);
        $lineage = (string) Str::uuid();
        DB::table('target_group_lineages')->insert(['lineage_id' => $lineage]);

        DB::table('audit_logs')->insert([
            'action' => 'SYN_FOUNDATION_EVENT', 'entity_type' => 'target_group_foundation',
            'created_at' => now(), 'import_request_id' => $requestId, 'content_object_id' => $contentId,
            'attempt_id' => $attemptId, 'lineage_id' => $lineage, 'version_token' => (string) Str::uuid(),
            'version_number' => 1, 'conflict_code' => 'SYN_CONFLICT', 'reconciliation_outcome' => 'SYN_REVIEW',
        ]);
        $this->assertDatabaseHas('audit_logs', ['action' => 'SYN_FOUNDATION_EVENT', 'import_request_id' => $requestId]);
    }

    private function insertRequest(string $requestId, string $operation): void
    {
        DB::table('import_requests')->insert([
            'import_request_id' => $requestId, 'operation' => $operation, 'lifecycle_state' => 'PENDING',
            'context_fingerprint' => hash('sha256', 'SYN_CONTEXT_'.$operation), 'correlation_id' => (string) Str::uuid(),
            'reconciliation_state' => 'NONE',
        ]);
    }

    private function assertQueryException(\Closure $operation): void
    {
        try {
            $operation();
        } catch (QueryException) {
            $this->assertTrue(true);
            return;
        }

        $this->fail('Expected a database constraint violation.');
    }

    private function insertJob(string $group, ?string $requestId = null, ?int $retryOf = null): int
    {
        return (int) DB::table('target_group_jobs')->insertGetId([
            'group_name' => $group, 'status' => 'PENDING', 'source_set_hash' => hash('sha256', 'SYN_SOURCE_'.$group),
            'import_request_id' => $requestId, 'retry_of_job_id' => $retryOf,
        ]);
    }

    private function insertFile(int $job, int $contentId, string $filename): int
    {
        return (int) DB::table('target_group_files')->insertGetId([
            'target_group_job_id' => $job, 'original_filename' => $filename, 'stored_path' => 'synthetic/'.$filename,
            'mime_type' => 'text/csv', 'size_bytes' => 10, 'sha256' => hash('sha256', $filename),
            'content_object_id' => $contentId,
        ]);
    }

    private function versionPrerequisites(string $suffix): array
    {
        $lineage = (string) Str::uuid();
        DB::table('target_group_lineages')->insert(['lineage_id' => $lineage]);
        $job = $this->insertJob($suffix.'_JOB');
        $content = DB::table('import_content_objects')->insertGetId(['sha256' => hash('sha256', $suffix.'_CONTENT'), 'byte_size' => 11]);
        $file = $this->insertFile($job, $content, $suffix.'.csv');
        return [$lineage, $job, $file];
    }

    private function insertVersion(string $lineage, int $job, int $file, string $token, int $number, ?int $previous = null): int
    {
        return (int) DB::table('target_group_file_versions')->insertGetId([
            'lineage_id' => $lineage, 'version_token' => $token, 'version_number' => $number,
            'target_group_file_id' => $file, 'target_group_job_id' => $job, 'previous_version_id' => $previous,
            'version_status' => 'CANDIDATE', 'correlation_id' => (string) Str::uuid(),
        ]);
    }
}
