<?php

namespace Tests\Feature;

use App\Models\TargetGroupFileVersion;
use App\Models\TargetGroupLineage;
use App\Services\Import\TargetGroupVersionAllocationService;
use Carbon\Carbon;
use Illuminate\Database\QueryException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;
use LogicException;
use Tests\TestCase;

final class TargetGroupD7D8VersionAllocationTest extends TestCase
{
    use RefreshDatabase;

    public function test_confirmed_at_is_nullable_and_persists_as_a_datetime(): void
    {
        $this->assertTrue(Schema::hasColumn('target_group_file_versions', 'confirmed_at'));

        [$lineage, $job, $file] = $this->versionPrerequisites('SYN_CONFIRMED_AT');
        $confirmedAt = Carbon::parse('2026-08-14 12:34:56');
        $id = $this->insertVersion($lineage, $job, $file, (string) Str::uuid(), 1, null, [
            'confirmed_at' => $confirmedAt,
        ]);

        $version = TargetGroupFileVersion::query()->findOrFail($id);

        $this->assertInstanceOf(Carbon::class, $version->confirmed_at);
        $this->assertSame($confirmedAt->toDateTimeString(), $version->confirmed_at->toDateTimeString());
    }

    public function test_allocator_assigns_sequential_numbers_and_independent_lineages(): void
    {
        $service = new TargetGroupVersionAllocationService();
        [$lineageA, $jobA, $fileA] = $this->versionPrerequisites('SYN_ALLOC_A');
        [$lineageB, $jobB, $fileB] = $this->versionPrerequisites('SYN_ALLOC_B');

        $first = $service->allocate($this->declaration($lineageA, $jobA, $fileA, $this->token()));
        $second = $service->allocate($this->declaration($lineageA, $jobA, $fileA, $this->token(), $first->getKey()));
        $other = $service->allocate($this->declaration($lineageB, $jobB, $fileB, $this->token()));

        $this->assertSame(1, $first->version_number);
        $this->assertSame(2, $second->version_number);
        $this->assertSame(1, $other->version_number);
        $this->assertSame(3, DB::table('target_group_lineages')->where('lineage_id', $lineageA)->value('next_version_number'));
        $this->assertSame(2, DB::table('target_group_lineages')->where('lineage_id', $lineageB)->value('next_version_number'));
    }

    public function test_existing_version_uniqueness_constraints_reject_duplicate_number_and_token(): void
    {
        [$lineage, $job, $file] = $this->versionPrerequisites('SYN_UNIQUE');
        $token = (string) Str::uuid();
        $this->insertVersion($lineage, $job, $file, $token, 1);

        $this->assertQueryException(fn () => $this->insertVersion($lineage, $job, $file, (string) Str::uuid(), 1));
        $this->assertQueryException(fn () => $this->insertVersion($lineage, $job, $file, $token, 2));
    }

    public function test_allocator_does_not_use_aggregate_version_number_allocation(): void
    {
        $path = base_path('app/Services/Import/TargetGroupVersionAllocationService.php');
        $this->assertFileExists($path);
        $source = strtolower((string) file_get_contents($path));

        $this->assertStringNotContainsString('max(', $source);
        $this->assertStringNotContainsString('count()+1', str_replace(' ', '', $source));
        $this->assertStringNotContainsString('last()->version_number', $source);
    }

    public function test_failed_creation_rolls_back_version_and_counter(): void
    {
        $service = new TargetGroupVersionAllocationService();
        [$lineage, $job, $file] = $this->versionPrerequisites('SYN_ROLLBACK');
        $existing = $this->insertVersion($lineage, $job, $file, (string) Str::uuid(), 1);

        try {
            $service->allocate($this->declaration($lineage, $job, $file, $this->token()));
            $this->fail('Expected the stale counter to trigger the existing unique constraint.');
        } catch (QueryException) {
            $this->assertSame(1, DB::table('target_group_lineages')->where('lineage_id', $lineage)->value('next_version_number'));
            $this->assertSame(1, DB::table('target_group_file_versions')->where('lineage_id', $lineage)->count());
            $this->assertDatabaseHas('target_group_file_versions', ['id' => $existing]);
        }
    }

    public function test_identity_fields_fail_explicitly_after_creation(): void
    {
        $service = new TargetGroupVersionAllocationService();
        [$lineage, $job, $file] = $this->versionPrerequisites('SYN_IMMUTABLE');
        $version = $service->allocate($this->declaration($lineage, $job, $file, $this->token()));
        $original = $version->getAttributes();

        foreach ([
            'lineage_id' => (string) Str::uuid(),
            'version_token' => (string) Str::uuid(),
            'version_number' => 999,
        ] as $field => $value) {
            $candidate = $version->fresh();
            $candidate->{$field} = $value;

            try {
                $candidate->save();
                $this->fail("Expected {$field} mutation to fail explicitly.");
            } catch (LogicException $exception) {
                $this->assertStringContainsString('immutable', strtolower($exception->getMessage()));
            }

            $this->assertSame($original[$field], $version->fresh()->getAttribute($field));
        }
    }

    public function test_same_token_and_same_context_is_a_safe_replay_without_counter_consumption(): void
    {
        $service = new TargetGroupVersionAllocationService();
        [$lineage, $job, $file] = $this->versionPrerequisites('SYN_REPLAY');
        $declaration = $this->declaration($lineage, $job, $file, $this->token());

        $first = $service->allocate($declaration);
        $replay = $service->allocate($declaration);

        $this->assertSame($first->getKey(), $replay->getKey());
        $this->assertSame(1, DB::table('target_group_file_versions')->where('lineage_id', $lineage)->count());
        $this->assertSame(2, DB::table('target_group_lineages')->where('lineage_id', $lineage)->value('next_version_number'));
    }

    public function test_same_token_with_conflicting_context_fails_closed_without_mutation(): void
    {
        $service = new TargetGroupVersionAllocationService();
        [$lineage, $job, $file] = $this->versionPrerequisites('SYN_TOKEN_CONFLICT');
        [, $otherJob, $otherFile] = $this->versionPrerequisites('SYN_TOKEN_CONFLICT_OTHER');
        $token = $this->token();
        $first = $service->allocate($this->declaration($lineage, $job, $file, $token));
        $counterBefore = DB::table('target_group_lineages')->where('lineage_id', $lineage)->value('next_version_number');

        try {
            $service->allocate($this->declaration($lineage, $otherJob, $otherFile, $token));
            $this->fail('Expected a token context conflict.');
        } catch (LogicException $exception) {
            $this->assertSame('VERSION_TOKEN_CONTEXT_CONFLICT', $exception->getMessage());
        }

        $this->assertSame(1, DB::table('target_group_file_versions')->where('lineage_id', $lineage)->count());
        $this->assertSame($counterBefore, DB::table('target_group_lineages')->where('lineage_id', $lineage)->value('next_version_number'));
        $this->assertDatabaseHas('target_group_file_versions', ['id' => $first->getKey(), 'version_token' => $token]);
    }

    public function test_allocator_does_not_activate_or_create_durable_import_or_history_state(): void
    {
        $service = new TargetGroupVersionAllocationService();
        [$lineage, $job, $file] = $this->versionPrerequisites('SYN_NO_SIDE_EFFECTS');
        $countsBefore = [
            'jobs' => DB::table('target_group_jobs')->count(),
            'files' => DB::table('target_group_files')->count(),
            'rows' => DB::table('target_group_rows')->count(),
            'history' => DB::table('target_group_history_rows')->count(),
            'supersessions' => DB::table('target_group_version_supersessions')->count(),
        ];

        $version = $service->allocate($this->declaration($lineage, $job, $file, $this->token()));

        $this->assertNull(DB::table('target_group_lineages')->where('lineage_id', $lineage)->value('active_version_id'));
        $this->assertSame($countsBefore, [
            'jobs' => DB::table('target_group_jobs')->count(),
            'files' => DB::table('target_group_files')->count(),
            'rows' => DB::table('target_group_rows')->count(),
            'history' => DB::table('target_group_history_rows')->count(),
            'supersessions' => DB::table('target_group_version_supersessions')->count(),
        ]);
        $this->assertDatabaseHas('target_group_file_versions', ['id' => $version->getKey(), 'version_status' => 'CANDIDATE']);
    }

    private function declaration(string $lineage, int $job, int $file, string $token, ?int $previous = null): array
    {
        return [
            'lineage_id' => $lineage,
            'version_token' => $token,
            'target_group_file_id' => $file,
            'target_group_job_id' => $job,
            'previous_version_id' => $previous,
            'correction_reason' => 'SYN_CORRECTION',
            'correlation_id' => (string) Str::uuid(),
        ];
    }

    private function token(): string
    {
        return (string) Str::uuid();
    }

    private function versionPrerequisites(string $name): array
    {
        $lineage = (string) Str::uuid();
        DB::table('target_group_lineages')->insert(['lineage_id' => $lineage]);
        $job = DB::table('target_group_jobs')->insertGetId([
            'group_name' => $name,
            'status' => 'PREVIEW',
        ]);
        $file = DB::table('target_group_files')->insertGetId([
            'target_group_job_id' => $job,
            'original_filename' => strtolower($name).'.csv',
            'stored_path' => 'synthetic/'.strtolower($name).'.csv',
            'mime_type' => 'text/csv',
            'size_bytes' => 8,
            'sha256' => hash('sha256', $name),
        ]);

        return [$lineage, $job, $file];
    }

    private function insertVersion(
        string $lineage,
        int $job,
        int $file,
        string $token,
        int $number,
        ?int $previous = null,
        array $extra = [],
    ): int {
        return DB::table('target_group_file_versions')->insertGetId(array_merge([
            'lineage_id' => $lineage,
            'version_token' => $token,
            'version_number' => $number,
            'target_group_file_id' => $file,
            'target_group_job_id' => $job,
            'previous_version_id' => $previous,
            'version_status' => 'CANDIDATE',
            'correlation_id' => (string) Str::uuid(),
        ], $extra));
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
}
