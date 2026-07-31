<?php

namespace Tests\Feature;

use App\Models\Permission;
use App\Models\Role;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class ExportGenerationTriggerTest extends TestCase
{
    use RefreshDatabase;

    protected function tearDown(): void
    {
        foreach ($this->exportFiles() as $file) {
            @unlink($file);
        }
        @rmdir(storage_path('app/exports'));
        parent::tearDown();
    }

    public function test_confirmation_invalid_ids_mismatch_categories_and_dangerous_fields_fail_closed(): void
    {
        $user = $this->createAuthorizedUser();
        $targetJobId = $this->createTargetGroupJob('technical-primary');
        $resultJobId = $this->createResultGenerationJob($targetJobId);
        $this->createResult($targetJobId, $resultJobId, 'has_history');
        $otherTargetId = $this->createTargetGroupJob('technical-other');
        $otherResultJobId = $this->createResultGenerationJob($otherTargetId);

        $cases = [
            [['target_group_job_id' => $targetJobId, 'result_generation_job_id' => $resultJobId], 'confirmed'],
            [['confirmed' => '1', 'target_group_job_id' => 999999, 'result_generation_job_id' => $resultJobId], 'target_group_job_id'],
            [['confirmed' => '1', 'target_group_job_id' => $targetJobId, 'result_generation_job_id' => 999999], 'result_generation_job_id'],
            [['confirmed' => '1', 'target_group_job_id' => $targetJobId, 'result_generation_job_id' => $otherResultJobId], 'result_generation_job_id'],
            [['confirmed' => '1', 'target_group_job_id' => $targetJobId, 'result_generation_job_id' => $resultJobId, 'categories' => ['not_allowed']], 'categories.0'],
            [['confirmed' => '1', 'target_group_job_id' => $targetJobId, 'result_generation_job_id' => $resultJobId, 'categories' => ['has_history', 'has_history']], 'categories.1'],
            [[
                'confirmed' => '1',
                'target_group_job_id' => $targetJobId,
                'result_generation_job_id' => $resultJobId,
                'requested_by_user_id' => 999999,
                'filename' => 'browser-controlled.csv',
                'stored_path' => 'public/browser-controlled.csv',
                'columns' => ['raw_cid'],
                'download' => '1',
                'policy_version' => 'identified_override',
            ], 'requested_by_user_id'],
        ];

        foreach ($cases as [$payload, $errorKey]) {
            $this->actingAs($user)
                ->from('/exports')
                ->post('/exports/generate', $payload)
                ->assertRedirect('/exports')
                ->assertSessionHasErrors($errorKey);
        }

        $this->assertDatabaseCount('export_jobs', 0);
        $this->assertDatabaseCount('audit_logs', 0);
        $this->assertSame([], $this->exportFiles());
    }

    public function test_authorized_confirmed_request_generates_private_artifact_with_safe_attribution_and_audit(): void
    {
        $user = $this->createAuthorizedUser();
        $targetJobId = $this->createTargetGroupJob();
        $resultJobId = $this->createResultGenerationJob($targetJobId);
        $resultId = $this->createResult($targetJobId, $resultJobId, 'has_history');
        $this->createSource($resultId);
        $resultCountBefore = DB::table('target_group_results')->count();
        $sourceCountBefore = DB::table('target_group_result_sources')->count();
        $generationCountBefore = DB::table('result_generation_jobs')->count();

        $response = $this->actingAs($user)->post('/exports/generate', [
            'confirmed' => 'yes',
            'target_group_job_id' => $targetJobId,
            'result_generation_job_id' => $resultJobId,
            'categories' => ['has_history'],
        ]);

        $response->assertRedirect(route('exports.index'))
            ->assertSessionHas('status')
            ->assertDontSee('stored_path')
            ->assertDontSee('exports/')
            ->assertDontSee('TECHNICAL_SOURCE_CONTENT_MUST_NOT_RENDER');

        $job = DB::table('export_jobs')->sole();
        $filters = json_decode($job->filters, true, flags: JSON_THROW_ON_ERROR);
        $path = storage_path('app/'.$job->stored_path);

        $this->assertSame('completed', $job->status);
        $this->assertSame($user->id, $job->requested_by_user_id);
        $this->assertSame('deidentified_internal_v1', $filters['policy_version']);
        $this->assertSame($targetJobId, $filters['target_group_job_id']);
        $this->assertSame($resultJobId, $filters['result_generation_job_id']);
        $this->assertSame(['has_history'], $filters['categories']);
        $this->assertArrayNotHasKey('columns', $filters);
        $this->assertArrayNotHasKey('filename', $filters);
        $this->assertFileExists($path);
        $this->assertSame(1, $job->row_count);
        $this->assertSame(filesize($path), $job->byte_count);
        $this->assertSame(hash_file('sha256', $path), $job->sha256);
        $this->assertSame($resultCountBefore, DB::table('target_group_results')->count());
        $this->assertSame($sourceCountBefore, DB::table('target_group_result_sources')->count());
        $this->assertSame($generationCountBefore, DB::table('result_generation_jobs')->count());

        $audit = DB::table('audit_logs')->where('action', 'export_csv_generated')->sole();
        $auditMetadata = json_decode($audit->after_payload, true, flags: JSON_THROW_ON_ERROR);
        $this->assertSame($user->id, $audit->actor_user_id);
        $this->assertSame('export_job', $audit->entity_type);
        $this->assertSame($job->id, $audit->entity_id);
        $this->assertSame('deidentified_internal_v1', $auditMetadata['policy_version']);
        $this->assertSame(1, DB::table('audit_logs')->where('action', 'export_csv_generated')->count());

        $page = $this->actingAs($user)->get('/exports');
        $page->assertOk()
            ->assertSee((string) $job->id)
            ->assertSee($job->sha256)
            ->assertDontSee($job->stored_path)
            ->assertDontSee($job->generated_filename)
            ->assertDontSee('TECHNICAL_SOURCE_CONTENT_MUST_NOT_RENDER');
    }

    public function test_staging_only_context_is_ineligible_and_creates_no_export_or_success_audit(): void
    {
        $user = $this->createAuthorizedUser();
        $targetJobId = $this->createTargetGroupJob();
        $resultJobId = $this->createResultGenerationJob($targetJobId);
        $this->createStagingRow($targetJobId);

        $this->actingAs($user)->post('/exports/generate', [
            'confirmed' => '1',
            'target_group_job_id' => $targetJobId,
            'result_generation_job_id' => $resultJobId,
        ])->assertRedirect(route('exports.index'))
            ->assertSessionHasErrors('export');

        $this->assertDatabaseCount('export_jobs', 0);
        $this->assertSame(0, DB::table('audit_logs')->where('action', 'export_csv_generated')->count());
        $this->assertSame([], $this->exportFiles());
    }

    public function test_controller_contains_no_export_business_logic_or_result_generation_dependency(): void
    {
        $controller = file_get_contents(app_path('Http/Controllers/ExportController.php'));

        foreach (['fputcsv', 'hash_file', 'storage_path', 'target_group_result_sources', 'ResultGenerationService', 'AuditLogger'] as $forbidden) {
            $this->assertStringNotContainsString($forbidden, $controller);
        }
    }

    private function createAuthorizedUser(): User
    {
        $user = User::create([
            'name' => 'EXPORT_TRIGGER_TEST_ACCOUNT',
            'email' => 'export-trigger-test@example.invalid',
            'password' => 'technical-test-password',
        ]);
        $role = Role::create(['name' => 'export-trigger-role']);
        $permission = Permission::firstOrCreate(['name' => 'export.generate']);
        $user->roles()->attach($role);
        $role->permissions()->attach($permission);

        return $user;
    }

    private function createTargetGroupJob(string $label = 'technical-target-group'): int
    {
        return DB::table('target_group_jobs')->insertGetId([
            'group_name' => $label,
            'status' => 'technical_ready',
            'total_files' => 0,
            'total_rows' => 0,
            'valid_rows' => 0,
            'invalid_rows' => 0,
            'review_rows' => 0,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function createResultGenerationJob(int $targetJobId): int
    {
        return DB::table('result_generation_jobs')->insertGetId([
            'target_group_job_id' => $targetJobId,
            'status' => 'completed',
            'selected_service_keys' => json_encode(['technical-service']),
            'normalization_version' => 1,
            'total_persons' => 1,
            'completed_persons' => 1,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function createResult(int $targetJobId, int $resultJobId, string $category): int
    {
        return DB::table('target_group_results')->insertGetId([
            'target_group_job_id' => $targetJobId,
            'result_generation_job_id' => $resultJobId,
            'person_key' => 'technical-key-'.uniqid(),
            'result_category' => $category,
            'has_screening_db_history' => $category === 'has_history',
            'has_target_group_file_history' => false,
            'has_any_history' => $category === 'has_history',
            'selected_service_keys' => json_encode(['ignored-result-copy']),
            'evidence_summary' => json_encode(['technical' => true]),
            'review_status' => 'technical_clear',
            'review_reason' => 'TECHNICAL_REVIEW_REASON_MUST_NOT_RENDER',
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function createSource(int $resultId): void
    {
        DB::table('target_group_result_sources')->insert([
            'target_group_result_id' => $resultId,
            'source_type' => 'technical_source',
            'source_payload' => json_encode(['TECHNICAL_SOURCE_CONTENT_MUST_NOT_RENDER']),
            'provenance' => json_encode(['TECHNICAL_PROVENANCE_MUST_NOT_RENDER']),
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function createStagingRow(int $targetJobId): void
    {
        $fileId = DB::table('target_group_files')->insertGetId([
            'target_group_job_id' => $targetJobId,
            'original_filename' => 'technical-no-file',
            'stored_path' => '__technical_no_file__',
            'mime_type' => 'text/plain',
            'size_bytes' => 0,
            'sha256' => hash('sha256', 'technical-staging-'.$targetJobId),
            'row_count' => 1,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        DB::table('target_group_rows')->insert([
            'target_group_job_id' => $targetJobId,
            'target_group_file_id' => $fileId,
            'row_number' => 1,
            'raw_payload' => json_encode(['technical_staging' => true]),
            'cid_status' => 'missing_identifier',
            'validation_status' => 'missing_identifier',
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function exportFiles(): array
    {
        return array_values(array_filter(glob(storage_path('app/exports/*')) ?: [], 'is_file'));
    }
}
