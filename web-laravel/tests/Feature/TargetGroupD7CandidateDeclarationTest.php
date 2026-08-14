<?php

namespace Tests\Feature;

use App\Models\AuditLog;
use App\Services\Import\TargetGroupFileVersionDeclarationService;
use Carbon\Carbon;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use LogicException;
use Tests\TestCase;

final class TargetGroupD7CandidateDeclarationTest extends TestCase
{
    use RefreshDatabase;

    public function test_valid_corrected_file_declaration_creates_one_candidate_and_audit(): void
    {
        $fixture = $this->correctionFixture();
        $declaration = $this->declaration($fixture);
        $reason = 'แก้ไขข้อมูลการคัดกรอง';
        $declaration['correction_reason'] = "  {$reason}  ";

        $candidate = $this->service()->declareCandidate($declaration);

        $this->assertSame('CANDIDATE', $candidate->version_status);
        $this->assertSame(2, $candidate->version_number);
        $this->assertSame($fixture['lineage'], $candidate->lineage_id);
        $this->assertSame($fixture['predecessor'], $candidate->previous_version_id);
        $this->assertSame($reason, $candidate->correction_reason);
        $this->assertSame($fixture['user'], $candidate->confirmed_by_user_id);
        $this->assertSame($declaration['confirmed_at']->toDateTimeString(), $candidate->confirmed_at->toDateTimeString());
        $this->assertSame($fixture['predecessor'], DB::table('target_group_lineages')->where('lineage_id', $fixture['lineage'])->value('active_version_id'));
        $this->assertSame(3, DB::table('target_group_lineages')->where('lineage_id', $fixture['lineage'])->value('next_version_number'));

        $audit = AuditLog::query()->where('action', 'FILE_VERSION_DECLARED')->sole();
        $this->assertSame($fixture['user'], $audit->actor_user_id);
        $this->assertSame($candidate->getKey(), $audit->version_id);
        $this->assertSame($candidate->getKey(), $audit->entity_id);
        $this->assertSame($fixture['lineage'], $audit->lineage_id);
        $this->assertSame($fixture['file'], $audit->target_group_file_id);
        $this->assertSame($fixture['job'], $audit->target_group_job_id);
        $this->assertSame($fixture['predecessor'], $audit->predecessor_version_id);
        $this->assertSame($candidate->version_token, $audit->version_token);
        $this->assertSame(2, $audit->version_number);
        $this->assertSame($reason, $audit->review_reason_code);
        $this->assertSame($declaration['correlation_id'], $audit->correlation_id);
        $this->assertSame($fixture['correctedSha'], $audit->after_payload['physical_sha256']);
        $this->assertArrayNotHasKey('raw_cid', $audit->after_payload);
        $this->assertArrayNotHasKey('patient', $audit->after_payload);
    }

    public function test_prior_version_physical_evidence_rows_reviews_and_active_pointer_are_preserved(): void
    {
        $fixture = $this->correctionFixture();
        DB::table('target_group_rows')->insert($this->rowPayload($fixture['predecessorJob'], $fixture['predecessorFile']));
        DB::table('target_group_row_reviews')->insert($this->reviewPayload($fixture['predecessorJob'], $fixture['predecessorFile']));
        $beforeVersion = DB::table('target_group_file_versions')->where('id', $fixture['predecessor'])->first();
        $beforeFile = DB::table('target_group_files')->where('id', $fixture['predecessorFile'])->first();
        $beforeRows = DB::table('target_group_rows')->count();
        $beforeReviews = DB::table('target_group_row_reviews')->count();

        $this->service()->declareCandidate($this->declaration($fixture));

        $afterVersion = DB::table('target_group_file_versions')->where('id', $fixture['predecessor'])->first();
        $afterFile = DB::table('target_group_files')->where('id', $fixture['predecessorFile'])->first();
        $this->assertEquals($beforeVersion, $afterVersion);
        $this->assertEquals($beforeFile, $afterFile);
        $this->assertSame($beforeRows, DB::table('target_group_rows')->count());
        $this->assertSame($beforeReviews, DB::table('target_group_row_reviews')->count());
        $this->assertSame($fixture['predecessor'], DB::table('target_group_lineages')->where('lineage_id', $fixture['lineage'])->value('active_version_id'));
        $this->assertSame(0, DB::table('target_group_version_supersessions')->count());
        $this->assertSame(0, DB::table('target_group_history_rows')->count());
    }

    public function test_predecessor_is_required_and_must_be_the_current_active_version(): void
    {
        $fixture = $this->correctionFixture();

        $missing = $this->declaration($fixture);
        unset($missing['previous_version_id']);
        $this->assertThrowsCode('PREDECESSOR_REQUIRED', fn () => $this->service()->declareCandidate($missing));

        $notCurrent = $this->declaration($fixture);
        $notCurrent['previous_version_id'] = $fixture['otherVersion'];
        $this->assertThrowsCode('PREDECESSOR_NOT_CURRENT_ACTIVE', fn () => $this->service()->declareCandidate($notCurrent));

        DB::table('target_group_lineages')->where('lineage_id', $fixture['lineage'])->update(['active_version_id' => null]);
        $this->assertThrowsCode('PREDECESSOR_NOT_APPLICABLE', fn () => $this->service()->declareCandidate($this->declaration($fixture)));
    }

    public function test_predecessor_must_be_in_the_same_lineage_and_active(): void
    {
        $fixture = $this->correctionFixture();

        $foreign = $this->declaration($fixture);
        $foreign['previous_version_id'] = $fixture['foreignVersion'];
        DB::table('target_group_lineages')->where('lineage_id', $fixture['lineage'])->update(['active_version_id' => $fixture['foreignVersion']]);
        $this->assertThrowsCode('PREDECESSOR_LINEAGE_MISMATCH', fn () => $this->service()->declareCandidate($foreign));

        foreach (['CANDIDATE', 'SUPERSEDED', 'REJECTED', 'VOIDED'] as $status) {
            $case = $this->correctionFixture();
            DB::table('target_group_file_versions')->where('id', $case['predecessor'])->update(['version_status' => $status]);
            $this->assertThrowsCode('PREDECESSOR_NOT_ACTIVE', fn () => $this->service()->declareCandidate($this->declaration($case)));
        }
    }

    public function test_corrected_sha_must_differ_and_physical_file_must_match_job(): void
    {
        $fixture = $this->correctionFixture();

        $sameSha = $this->declaration($fixture);
        DB::table('target_group_files')->where('id', $fixture['file'])->update(['sha256' => $fixture['predecessorSha']]);
        $this->assertThrowsCode('CORRECTED_SHA_MUST_DIFFER', fn () => $this->service()->declareCandidate($sameSha));

        $mismatch = $this->correctionFixture();
        $mismatchDeclaration = $this->declaration($mismatch);
        $mismatchDeclaration['target_group_job_id'] = $mismatch['predecessorJob'];
        $this->assertThrowsCode('PHYSICAL_FILE_JOB_MISMATCH', fn () => $this->service()->declareCandidate($mismatchDeclaration));

        $missing = $this->declaration($mismatch);
        $missing['target_group_file_id'] = 999999;
        $this->assertThrowsCode('PHYSICAL_FILE_NOT_FOUND', fn () => $this->service()->declareCandidate($missing));
    }

    public function test_reason_is_trimmed_unicode_and_limited_to_64_characters(): void
    {
        $fixture = $this->correctionFixture();
        $declaration = $this->declaration($fixture);
        $declaration['correction_reason'] = "  แก้ไขข้อมูล  ";
        $candidate = $this->service()->declareCandidate($declaration);
        $this->assertSame('แก้ไขข้อมูล', $candidate->correction_reason);

        foreach (['', '   ', str_repeat('x', 65)] as $reason) {
            $case = $this->correctionFixture();
            $invalid = $this->declaration($case);
            $invalid['correction_reason'] = $reason;
            $code = trim($reason) === '' ? 'CORRECTION_REASON_REQUIRED' : 'CORRECTION_REASON_TOO_LONG';
            $this->assertThrowsCode($code, fn () => $this->service()->declareCandidate($invalid));
        }
    }

    public function test_confirmation_identity_and_timestamp_are_required_and_persisted(): void
    {
        $fixture = $this->correctionFixture();

        $missingUser = $this->declaration($fixture);
        unset($missingUser['confirmed_by_user_id']);
        $this->assertThrowsCode('CONFIRMED_BY_USER_REQUIRED', fn () => $this->service()->declareCandidate($missingUser));

        $unknownUser = $this->declaration($fixture);
        $unknownUser['confirmed_by_user_id'] = 999999;
        $this->assertThrowsCode('CONFIRMING_USER_NOT_FOUND', fn () => $this->service()->declareCandidate($unknownUser));

        $missingTime = $this->declaration($fixture);
        unset($missingTime['confirmed_at']);
        $this->assertThrowsCode('CONFIRMED_AT_REQUIRED', fn () => $this->service()->declareCandidate($missingTime));

        $candidate = $this->service()->declareCandidate($this->declaration($fixture));
        $this->assertSame($fixture['user'], $candidate->confirmed_by_user_id);
        $this->assertNotNull($candidate->confirmed_at);
    }

    public function test_same_token_exact_context_replays_without_new_version_or_audit(): void
    {
        $fixture = $this->correctionFixture();
        $declaration = $this->declaration($fixture);
        $first = $this->service()->declareCandidate($declaration);
        $counter = DB::table('target_group_lineages')->where('lineage_id', $fixture['lineage'])->value('next_version_number');
        $auditCount = AuditLog::query()->where('action', 'FILE_VERSION_DECLARED')->count();

        $replay = $this->service()->declareCandidate($declaration);

        $this->assertSame($first->getKey(), $replay->getKey());
        $this->assertSame(3, DB::table('target_group_file_versions')->where('lineage_id', $fixture['lineage'])->count());
        $this->assertSame($counter, DB::table('target_group_lineages')->where('lineage_id', $fixture['lineage'])->value('next_version_number'));
        $this->assertSame($auditCount, AuditLog::query()->where('action', 'FILE_VERSION_DECLARED')->count());
    }

    public function test_same_token_context_conflicts_fail_closed_without_mutation(): void
    {
        $fixture = $this->correctionFixture();
        $declaration = $this->declaration($fixture);
        $first = $this->service()->declareCandidate($declaration);
        $counter = DB::table('target_group_lineages')->where('lineage_id', $fixture['lineage'])->value('next_version_number');

        foreach ([
            'confirmed_by_user_id' => $this->createUser('other@example.test'),
            'confirmed_at' => Carbon::parse('2026-08-14 13:00:00'),
            'correction_reason' => 'different reason',
            'previous_version_id' => $fixture['otherVersion'],
            'target_group_file_id' => $fixture['otherFile'],
            'target_group_job_id' => $fixture['otherJob'],
            'lineage_id' => $fixture['foreignLineage'],
        ] as $field => $value) {
            $conflict = $declaration;
            $conflict[$field] = $value;
            $this->assertThrowsCode('VERSION_TOKEN_CONTEXT_CONFLICT', fn () => $this->service()->declareCandidate($conflict));
        }

        $this->assertSame(1, DB::table('target_group_file_versions')->where('id', $first->getKey())->count());
        $this->assertSame($counter, DB::table('target_group_lineages')->where('lineage_id', $fixture['lineage'])->value('next_version_number'));
        $this->assertSame(1, AuditLog::query()->where('action', 'FILE_VERSION_DECLARED')->count());
    }

    public function test_audit_failure_rolls_back_candidate_and_counter(): void
    {
        $fixture = $this->correctionFixture();
        AuditLog::creating(function (): void {
            throw new LogicException('SYN_AUDIT_FAILURE');
        });

        try {
            $this->assertThrowsCode('SYN_AUDIT_FAILURE', fn () => $this->service()->declareCandidate($this->declaration($fixture)));
        } finally {
            AuditLog::flushEventListeners();
        }

        $this->assertSame(2, DB::table('target_group_file_versions')->where('lineage_id', $fixture['lineage'])->count());
        $this->assertSame(2, DB::table('target_group_lineages')->where('lineage_id', $fixture['lineage'])->value('next_version_number'));
        $this->assertSame(0, AuditLog::query()->where('action', 'FILE_VERSION_DECLARED')->count());
        $this->assertSame(0, DB::table('target_group_version_supersessions')->count());
    }

    private function service(): TargetGroupFileVersionDeclarationService
    {
        return new TargetGroupFileVersionDeclarationService();
    }

    private function declaration(array $fixture): array
    {
        return [
            'lineage_id' => $fixture['lineage'],
            'version_token' => (string) Str::uuid(),
            'target_group_file_id' => $fixture['file'],
            'target_group_job_id' => $fixture['job'],
            'previous_version_id' => $fixture['predecessor'],
            'correction_reason' => 'SYN_CORRECTION',
            'confirmed_by_user_id' => $fixture['user'],
            'confirmed_at' => Carbon::parse('2026-08-14 12:34:56'),
            'correlation_id' => (string) Str::uuid(),
        ];
    }

    private function correctionFixture(): array
    {
        $user = $this->createUser();
        $lineage = (string) Str::uuid();
        $foreignLineage = (string) Str::uuid();
        DB::table('target_group_lineages')->insert([
            'lineage_id' => $lineage,
            'next_version_number' => 2,
            'active_version_id' => null,
        ]);
        DB::table('target_group_lineages')->insert(['lineage_id' => $foreignLineage]);

        $predecessorJob = $this->createJob('SYN_PREDECESSOR');
        $predecessorFile = $this->createFile($predecessorJob, 'predecessor.csv', 'SYN_PREDECESSOR_BYTES');
        $predecessorSha = (string) DB::table('target_group_files')->where('id', $predecessorFile)->value('sha256');
        $predecessor = $this->createVersion($lineage, $predecessorJob, $predecessorFile, 'ACTIVE', 1);
        DB::table('target_group_lineages')->where('lineage_id', $lineage)->update(['active_version_id' => $predecessor]);

        $job = $this->createJob('SYN_CORRECTED');
        $file = $this->createFile($job, 'corrected.csv', 'SYN_CORRECTED_BYTES');
        $correctedSha = (string) DB::table('target_group_files')->where('id', $file)->value('sha256');

        $otherJob = $this->createJob('SYN_OTHER');
        $otherFile = $this->createFile($otherJob, 'other.csv', 'SYN_OTHER_BYTES');
        $otherVersion = $this->createVersion($lineage, $otherJob, $otherFile, 'CANDIDATE', 99);
        $foreignJob = $this->createJob('SYN_FOREIGN');
        $foreignFile = $this->createFile($foreignJob, 'foreign.csv', 'SYN_FOREIGN_BYTES');
        $foreignVersion = $this->createVersion($foreignLineage, $foreignJob, $foreignFile, 'ACTIVE', 1);

        return compact(
            'user', 'lineage', 'foreignLineage', 'predecessorJob', 'predecessorFile',
            'predecessorSha', 'predecessor', 'job', 'file', 'correctedSha',
            'otherJob', 'otherFile', 'otherVersion', 'foreignJob', 'foreignFile', 'foreignVersion'
        );
    }

    private function createUser(string $email = ''): int
    {
        $email = $email !== '' ? $email : 'operator-'.Str::uuid().'@example.test';

        return (int) DB::table('users')->insertGetId([
            'name' => 'Synthetic Operator',
            'email' => $email,
            'password' => password_hash('synthetic-test-only', PASSWORD_BCRYPT),
        ]);
    }

    private function createJob(string $name): int
    {
        return (int) DB::table('target_group_jobs')->insertGetId([
            'group_name' => $name,
            'status' => 'PREVIEW',
        ]);
    }

    private function createFile(int $job, string $filename, string $bytes): int
    {
        return (int) DB::table('target_group_files')->insertGetId([
            'target_group_job_id' => $job,
            'original_filename' => $filename,
            'stored_path' => 'synthetic/'.$filename,
            'mime_type' => 'text/csv',
            'size_bytes' => strlen($bytes),
            'sha256' => hash('sha256', $bytes),
        ]);
    }

    private function createVersion(string $lineage, int $job, int $file, string $status, int $number): int
    {
        return (int) DB::table('target_group_file_versions')->insertGetId([
            'lineage_id' => $lineage,
            'version_token' => (string) Str::uuid(),
            'version_number' => $number,
            'target_group_file_id' => $file,
            'target_group_job_id' => $job,
            'version_status' => $status,
            'correction_reason' => $status === 'ACTIVE' ? null : 'SYN_EXISTING',
            'correlation_id' => (string) Str::uuid(),
        ]);
    }

    private function rowPayload(int $job, int $file): array
    {
        return [
            'target_group_job_id' => $job,
            'target_group_file_id' => $file,
            'sheet_name' => 'Sheet1',
            'row_number' => 1,
            'raw_payload' => json_encode(['synthetic' => true]),
            'cid_status' => 'NOT_EVALUATED',
            'validation_status' => 'PENDING',
        ];
    }

    private function reviewPayload(int $job, int $file): array
    {
        return [
            'target_group_job_id' => $job,
            'target_group_file_id' => $file,
            'target_group_row_id' => DB::table('target_group_rows')->where('target_group_file_id', $file)->value('id'),
            'correlation_id' => (string) Str::uuid(),
            'from_status' => 'PENDING_VALIDATION',
            'to_status' => 'NEEDS_REVIEW',
            'review_reason_code' => 'SYN_REASON',
            'created_at' => now(),
        ];
    }

    private function assertThrowsCode(string $code, callable $operation): void
    {
        try {
            $operation();
            $this->fail("Expected {$code}.");
        } catch (LogicException $exception) {
            $this->assertSame($code, $exception->getMessage());
        }
    }
}
