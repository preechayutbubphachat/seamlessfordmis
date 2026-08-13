<?php

namespace Tests\Feature;

use App\Models\Permission;
use App\Models\Role;
use App\Models\User;
use Illuminate\Foundation\Http\Middleware\PreventRequestForgery;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

final class ImportPreviewUploadTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutMiddleware(PreventRequestForgery::class);

        $user = User::create([
            'name' => 'SYNTHETIC_IMPORT_PREVIEW',
            'email' => 'synthetic-import-preview@example.invalid',
            'password' => 'technical-test-password',
        ]);
        $role = Role::create(['name' => 'synthetic-import-preview-role']);
        $user->roles()->attach($role);
        foreach (['import.source.preview', 'import.source.commit', 'import.targetgroup.preview', 'import.targetgroup.commit'] as $name) {
            $permission = Permission::firstOrCreate(['name' => $name]);
            $role->permissions()->attach($permission);
        }
        $this->actingAs($user);
    }

    public function test_get_preview_forms_return_success(): void
    {
        $this->get('/imports/source-files/preview')
            ->assertOk()
            ->assertSee('Source File CSV Preview')
            ->assertSee('Preview-only');

        $this->get('/imports/target-groups/preview')
            ->assertOk()
            ->assertSee('Target Group CSV Preview')
            ->assertSee('Preview-only');
    }

    public function test_valid_synthetic_source_csv_upload_returns_preview_summary(): void
    {
        Storage::fake('local');

        $response = $this->post('/imports/source-files/preview', [
            'file' => $this->csvFile("cid,service_key\n1234567890121,SYN_ALPHA"),
        ]);

        $response
            ->assertOk()
            ->assertSee('Preview Summary')
            ->assertSee('Total Rows')
            ->assertSee('1')
            ->assertSee('valid')
            ->assertSee('1234567890121')
            ->assertSee('SYN_ALPHA');

        $this->assertNoPreviewSideEffects();
    }

    public function test_target_group_preview_shows_invalid_and_missing_identifier_statuses(): void
    {
        Storage::fake('local');
        $before = $this->tableCounts();

        $response = $this->post('/imports/target-groups/preview', [
            'file' => $this->csvFile("cid,full_name,marker\n1234567890129,SYN_NAME,SYN_INVALID\n,SYN_NAME,SYN_MISSING"),
        ]);

        $response
            ->assertOk()
            ->assertSee('invalid_identifier')
            ->assertSee('missing_identifier')
            ->assertSee('SYN_INVALID')
            ->assertSee('SYN_MISSING')
            ->assertSee('DURABLE_COMMIT_AVAILABLE: NO')
            ->assertSee('การแสดงตัวอย่าง Target Group เป็นแบบอ่านอย่างเดียว');

        $this->assertSame($before, $this->tableCounts());
        $this->assertNoPreviewSideEffects();
    }

    public function test_xlsx_upload_is_rejected(): void
    {
        $response = $this->from('/imports/source-files/preview')
            ->post('/imports/source-files/preview', [
                'file' => UploadedFile::fake()->create('synthetic.xlsx', 1, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ]);

        $response
            ->assertRedirect('/imports/source-files/preview')
            ->assertSessionHasErrors('file');
    }

    public function test_oversized_csv_upload_is_rejected(): void
    {
        $response = $this->from('/imports/target-groups/preview')
            ->post('/imports/target-groups/preview', [
                'file' => UploadedFile::fake()->create('synthetic.csv', 1025, 'text/csv'),
            ]);

        $response
            ->assertRedirect('/imports/target-groups/preview')
            ->assertSessionHasErrors('file');
    }

    public function test_post_preview_does_not_insert_staging_result_or_export_rows(): void
    {
        Storage::fake('local');

        $before = $this->tableCounts();

        $this->post('/imports/source-files/preview', [
            'file' => $this->csvFile("cid,service_key\n1234567890121,SYN_ALPHA"),
        ])->assertOk();

        $this->assertSame($before, $this->tableCounts());
        $this->assertNoPreviewSideEffects();
    }

    public function test_valid_source_import_is_staged_and_reconciled(): void
    {
        Storage::fake('local');

        $response = $this->post('/imports/source-files', [
            'files' => [
                $this->csvFile("cid,service_key\n1234567890121,SYN_ALPHA"),
            ],
        ]);

        $response
            ->assertOk()
            ->assertJsonStructure([
                'message',
                'source_import_job_id',
                'source_file_ids',
                'sha256',
                'rows_inserted',
                'status',
                'reconciliation',
                'file_stored',
                'patient_data_imported',
            ])
            ->assertJson([
                'message' => 'Source import completed successfully.',
                'file_stored' => true,
                'patient_data_imported' => false,
                'status' => 'completed',
            ]);

        $this->assertDatabaseCount('source_import_jobs', 1);
        $this->assertDatabaseCount('source_import_files', 1);
        $this->assertDatabaseCount('source_import_rows', 1);

        $job = DB::table('source_import_jobs')->first();
        $this->assertSame('completed', $job->status);
        $this->assertSame(1, $job->total_files);
        $this->assertSame(1, $job->total_rows);
        $this->assertSame(1, $job->valid_rows);
        $this->assertSame(0, $job->invalid_rows);
        $this->assertSame(0, $job->review_rows);
        // sha256 is stored on source_import_files, not source_import_jobs
        $file = DB::table('source_import_files')->first();
        $this->assertNotNull($file->sha256);

        Storage::disk('local')->assertMissing('blocked.txt');
        Storage::disk('local')->assertMissing('imports/blocked.txt');
    }

    public function test_invalid_source_import_is_rejected_without_persistence(): void
    {
        Storage::fake('local');

        // Missing 'files' array - FormRequest validation rejects with 302 redirect + session errors
        $response = $this->post('/imports/source-files', [
            'file' => UploadedFile::fake()->create('blocked.txt', 1, 'text/plain'),
        ]);

        $response->assertStatus(302);
        $response->assertSessionHasErrors('files');

        $this->assertDatabaseCount('source_import_jobs', 0);
        $this->assertDatabaseCount('source_import_files', 0);
        $this->assertDatabaseCount('source_import_rows', 0);

        // Non-CSV file - FormRequest passes (allows text/plain), controller returns 501
        $response = $this->post('/imports/source-files', [
            'files' => [
                UploadedFile::fake()->create('blocked.txt', 1, 'text/plain'),
            ],
        ]);

        $response->assertStatus(501);
        $response->assertJson([
            'message' => 'Import execution is not enabled in W4.',
            'file_stored' => false,
            'patient_data_imported' => false,
        ]);

        $this->assertDatabaseCount('source_import_jobs', 0);
        $this->assertDatabaseCount('source_import_files', 0);
        $this->assertDatabaseCount('source_import_rows', 0);

        Storage::disk('local')->assertMissing('blocked.txt');
        Storage::disk('local')->assertMissing('imports/blocked.txt');
    }

    public function test_source_import_post_uses_functional_import_contract(): void
    {
        Storage::fake('local');

        // Verify the route uses the new 'files' array contract, not old 'file' singular
        $response = $this->post('/imports/source-files', [
            'files' => [
                $this->csvFile("cid,service_key\n1234567890121,SYN_ALPHA"),
            ],
        ]);

        $response->assertOk();
        $response->assertJson([
            'file_stored' => true,
            'patient_data_imported' => false,
        ]);

        // Target groups route still returns 501 (not implemented in this slice)
        $this->post('/imports/target-groups', [
            'files' => [
                $this->csvFile("cid,marker\n1234567890121,SYN_ALPHA"),
            ],
        ])->assertStatus(501);

        Storage::disk('local')->assertMissing('blocked.txt');
        Storage::disk('local')->assertMissing('imports/blocked.txt');
    }

    private function csvFile(string $content): UploadedFile
    {
        return UploadedFile::fake()->createWithContent('synthetic.csv', $content);
    }

    private function tableCounts(): array
    {
        return [
            'source_import_jobs' => DB::table('source_import_jobs')->count(),
            'source_import_files' => DB::table('source_import_files')->count(),
            'source_import_rows' => DB::table('source_import_rows')->count(),
            'target_group_jobs' => DB::table('target_group_jobs')->count(),
            'target_group_files' => DB::table('target_group_files')->count(),
            'target_group_rows' => DB::table('target_group_rows')->count(),
            'result_generation_jobs' => DB::table('result_generation_jobs')->count(),
            'target_group_results' => DB::table('target_group_results')->count(),
            'target_group_result_sources' => DB::table('target_group_result_sources')->count(),
            'export_jobs' => DB::table('export_jobs')->count(),
        ];
    }

    private function assertNoPreviewSideEffects(): void
    {
        Storage::disk('local')->assertMissing('imports/synthetic.csv');
        Storage::disk('local')->assertMissing('imports/synthetic.xlsx');
        Storage::disk('local')->assertMissing('exports/synthetic.csv');
        Storage::disk('local')->assertMissing('exports/synthetic.xlsx');
    }
}
