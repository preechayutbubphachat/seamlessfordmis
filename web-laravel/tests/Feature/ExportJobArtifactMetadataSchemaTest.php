<?php

namespace Tests\Feature;

use App\Models\ExportJob;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Tests\TestCase;

final class ExportJobArtifactMetadataSchemaTest extends TestCase
{
    use RefreshDatabase;

    public function test_artifact_metadata_columns_exist_and_are_nullable(): void
    {
        $this->assertTrue(Schema::hasColumns('export_jobs', [
            'generated_filename',
            'mime_type',
            'byte_count',
            'sha256',
        ]));

        $jobId = DB::table('export_jobs')->insertGetId([
            'export_type' => 'synthetic_contract_check',
            'status' => 'blocked_not_implemented',
            'filters' => json_encode(['scope' => 'synthetic']),
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $job = DB::table('export_jobs')->find($jobId);

        $this->assertNull($job->generated_filename);
        $this->assertNull($job->mime_type);
        $this->assertNull($job->byte_count);
        $this->assertNull($job->sha256);
    }

    public function test_model_persists_metadata_in_dedicated_columns(): void
    {
        $sha256 = str_repeat('a', 64);
        $job = ExportJob::create([
            'export_type' => 'synthetic_contract_check',
            'status' => 'metadata_only',
            'filters' => ['categories' => ['has_history']],
            'generated_filename' => 'export-job-synthetic.csv',
            'mime_type' => 'text/csv',
            'byte_count' => 5_000_000_000,
            'sha256' => $sha256,
        ])->fresh();

        $this->assertSame(['categories' => ['has_history']], $job->filters);
        $this->assertSame('export-job-synthetic.csv', $job->generated_filename);
        $this->assertSame('text/csv', $job->mime_type);
        $this->assertSame(5_000_000_000, $job->byte_count);
        $this->assertSame($sha256, $job->sha256);
        $this->assertArrayNotHasKey('generated_filename', $job->filters);
        $this->assertArrayNotHasKey('sha256', $job->filters);
    }

    public function test_migration_defines_exact_types_and_scoped_rollback(): void
    {
        $migration = file_get_contents(database_path(
            'migrations/2026_07_14_000001_add_artifact_metadata_to_export_jobs_table.php'
        ));

        $this->assertSame(2, substr_count($migration, "Schema::table('export_jobs'"));
        $this->assertStringContainsString("string('generated_filename')->nullable()", $migration);
        $this->assertStringContainsString("string('mime_type', 100)->nullable()", $migration);
        $this->assertStringContainsString("unsignedBigInteger('byte_count')->nullable()", $migration);
        $this->assertStringContainsString("char('sha256', 64)->nullable()", $migration);
        $this->assertStringNotContainsString('unique(', $migration);
        $this->assertStringNotContainsString('dropIfExists', $migration);

        preg_match('/dropColumn\(\[(.*?)\]\);/s', $migration, $rollback);
        preg_match_all("/'([^']+)'/", $rollback[1] ?? '', $droppedColumns);

        $this->assertSame([
            'generated_filename',
            'mime_type',
            'byte_count',
            'sha256',
        ], $droppedColumns[1] ?? []);
    }

    public function test_model_has_no_filename_or_path_generation_behavior(): void
    {
        $methods = get_class_methods(ExportJob::class);

        $this->assertNotContains('generateFilename', $methods);
        $this->assertNotContains('generatePath', $methods);
        $this->assertNotContains('download', $methods);
    }
}
