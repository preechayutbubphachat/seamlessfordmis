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

final class ImportSafetyContractTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutMiddleware(PreventRequestForgery::class);

        $user = User::create([
            'name' => 'SYNTHETIC_IMPORT_SAFETY',
            'email' => 'synthetic-import-safety@example.invalid',
            'password' => 'technical-test-password',
        ]);
        $role = Role::create(['name' => 'synthetic-import-safety-role']);
        $user->roles()->attach($role);
        foreach (['import.source.view', 'import.source.commit', 'import.targetgroup.view', 'import.targetgroup.commit'] as $name) {
            $permission = Permission::firstOrCreate(['name' => $name]);
            $role->permissions()->attach($permission);
        }
        $this->actingAs($user);
    }

    private function csvFile(string $content): UploadedFile
    {
        return UploadedFile::fake()->createWithContent('synthetic.csv', $content);
    }

    public function test_import_placeholder_routes_return_success_without_patient_data(): void
    {
        $this->get('/imports/source-files')
            ->assertOk()
            ->assertSee('Source Files')
            ->assertSee('No real patient data')
            ->assertSee('No upload form is available');

        $this->get('/imports/source-files/1')
            ->assertOk()
            ->assertSee('Source Import Job Detail')
            ->assertSee('No records loaded');

        $this->get('/imports/target-groups')
            ->assertOk()
            ->assertSee('Target Group Imports')
            ->assertSee('No real patient data')
            ->assertSee('No upload form is available');

        $this->get('/imports/target-groups/1')
            ->assertOk()
            ->assertSee('Target Group Import Job Detail')
            ->assertSee('No records loaded');
    }

    public function test_source_import_post_is_blocked_and_stores_no_file_or_rows(): void
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

        Storage::disk('local')->assertMissing('blocked.txt');
        Storage::disk('local')->assertMissing('imports/blocked.txt');
    }

    public function test_source_import_post_rejects_invalid_request_without_persistence(): void
    {
        Storage::fake('local');

        // Missing 'files' array (old 'file' key) - FormRequest validation rejects with 302 redirect + session errors
        $response = $this->post('/imports/source-files', [
            'file' => $this->csvFile("cid,service_key\n1234567890121,SYN_ALPHA"),
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

    public function test_target_group_import_post_is_blocked_and_stores_no_file_or_rows(): void
    {
        Storage::fake('local');

        $response = $this->post('/imports/target-groups', [
            'file' => UploadedFile::fake()->create('blocked.txt', 1, 'text/plain'),
        ]);

        $response
            ->assertStatus(501)
            ->assertJson([
                'message' => 'Import execution is not enabled in W4.',
                'file_stored' => false,
                'patient_data_imported' => false,
            ]);

        Storage::disk('local')->assertMissing('blocked.txt');
        $this->assertSame(0, DB::table('target_group_jobs')->count());
        $this->assertSame(0, DB::table('target_group_files')->count());
        $this->assertSame(0, DB::table('target_group_rows')->count());
        $this->assertSame(0, DB::table('target_group_history_rows')->count());
    }
}
