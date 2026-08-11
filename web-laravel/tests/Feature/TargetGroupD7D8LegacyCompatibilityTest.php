<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Database\QueryException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Tests\TestCase;

final class TargetGroupD7D8LegacyCompatibilityTest extends TestCase
{
    use RefreshDatabase;

    public function test_legacy_target_group_rows_keep_new_identity_columns_nullable_without_backfill(): void
    {
        $job = DB::table('target_group_jobs')->insertGetId(['group_name' => 'SYN_LEGACY', 'status' => 'PREVIEW']);
        $file = DB::table('target_group_files')->insertGetId([
            'target_group_job_id' => $job, 'original_filename' => 'legacy.csv', 'stored_path' => 'synthetic/legacy.csv',
            'mime_type' => 'text/csv', 'size_bytes' => 8, 'sha256' => hash('sha256', 'SYN_LEGACY_FILE'),
        ]);

        $this->assertNull(DB::table('target_group_jobs')->where('id', $job)->value('import_request_id'));
        $this->assertNull(DB::table('target_group_jobs')->where('id', $job)->value('retry_of_job_id'));
        $this->assertNull(DB::table('target_group_files')->where('id', $file)->value('content_object_id'));
        $this->assertSame(0, DB::table('target_group_file_versions')->count());
        $this->assertSame(0, DB::table('target_group_lineages')->count());
    }

    public function test_legacy_evidence_delete_is_restrictive_not_cascading(): void
    {
        $job = DB::table('target_group_jobs')->insertGetId(['group_name' => 'SYN_RESTRICT', 'status' => 'PREVIEW']);
        DB::table('target_group_files')->insert([
            'target_group_job_id' => $job, 'original_filename' => 'restrict.csv', 'stored_path' => 'synthetic/restrict.csv',
            'mime_type' => 'text/csv', 'size_bytes' => 8, 'sha256' => hash('sha256', 'SYN_RESTRICT_FILE'),
        ]);

        $this->assertQueryException(fn () => DB::table('target_group_jobs')->where('id', $job)->delete());
        $this->assertDatabaseHas('target_group_jobs', ['id' => $job]);
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

    public function test_foundation_schema_is_present_and_empty_schema_rollback_contract_is_declared(): void
    {
        $this->assertTrue(Schema::hasTable('import_content_objects'));
        $this->assertTrue(Schema::hasTable('import_requests'));
        $this->assertTrue(Schema::hasTable('target_group_job_attempts'));
        $this->assertTrue(Schema::hasTable('target_group_lineages'));
        $this->assertTrue(Schema::hasTable('target_group_file_versions'));
        $this->assertTrue(Schema::hasTable('target_group_version_supersessions'));
        $this->assertSame(0, DB::table('import_content_objects')->count());
        $this->assertSame(0, DB::table('import_requests')->count());
        $this->assertSame(0, DB::table('target_group_job_attempts')->count());
        $this->assertSame(0, DB::table('target_group_lineages')->count());
        $this->assertSame(0, DB::table('target_group_file_versions')->count());
        $this->assertSame(0, DB::table('target_group_version_supersessions')->count());
    }
}
