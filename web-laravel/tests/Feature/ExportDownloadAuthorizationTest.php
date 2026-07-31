<?php

namespace Tests\Feature;

use App\Models\ExportJob;
use App\Models\Permission;
use App\Models\Role;
use App\Models\User;
use Database\Seeders\SystemPermissionSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class ExportDownloadAuthorizationTest extends TestCase
{
    use RefreshDatabase;

    private array $artifacts = [];

    protected function tearDown(): void
    {
        foreach ($this->artifacts as $path) {
            if (is_file($path) || is_link($path)) {
                @unlink($path);
            }
        }

        @rmdir(storage_path('app/exports'));
        parent::tearDown();
    }

    public function test_guest_is_redirected_to_named_login(): void
    {
        $job = $this->completedJob($this->createUser('download-owner@example.invalid'));

        $this->get(route('exports.download', $job))->assertRedirect(route('login'));

        $this->assertDatabaseMissing('audit_logs', ['action' => 'export_csv_downloaded']);
    }

    public function test_authenticated_user_without_permission_is_forbidden(): void
    {
        $owner = $this->createUser('download-denied@example.invalid');
        $job = $this->completedJob($owner);

        $this->actingAs($owner)->get(route('exports.download', $job))->assertForbidden();

        $this->assertDatabaseMissing('audit_logs', ['action' => 'export_csv_downloaded']);
    }

    public function test_permitted_non_owner_is_forbidden(): void
    {
        $job = $this->completedJob($this->createUser('download-other-owner@example.invalid'));
        $nonOwner = $this->createAuthorizedUser('download-non-owner@example.invalid');

        $this->actingAs($nonOwner)->get(route('exports.download', $job))->assertForbidden();

        $this->assertDatabaseMissing('audit_logs', ['action' => 'export_csv_downloaded']);
    }

    public function test_permitted_owner_downloads_verified_private_csv_and_writes_safe_audit(): void
    {
        $owner = $this->createAuthorizedUser('download-allowed@example.invalid');
        $bytes = "result_category,total\nmatched,3\n";
        $job = $this->completedJob($owner, $bytes);

        $response = $this->actingAs($owner)->get(route('exports.download', $job));

        $response->assertOk()->assertDownload($job->generated_filename);
        $this->assertSame($bytes, $response->streamedContent());

        $audit = DB::table('audit_logs')->where('action', 'export_csv_downloaded')->sole();
        $this->assertSame($owner->id, $audit->actor_user_id);
        $this->assertSame('export_job', $audit->entity_type);
        $this->assertSame($job->id, $audit->entity_id);
        $payload = json_decode($audit->after_payload, true, flags: JSON_THROW_ON_ERROR);
        $this->assertSame([
            'byte_count' => strlen($bytes),
            'sha256' => hash('sha256', $bytes),
        ], $payload);
        $this->assertStringNotContainsString('exports/', $audit->after_payload);
        $this->assertStringNotContainsString('result_category', $audit->after_payload);
    }

    public function test_missing_artifact_fails_closed_without_audit_or_path_disclosure(): void
    {
        $owner = $this->createAuthorizedUser('download-missing@example.invalid');
        $job = $this->completedJob($owner);
        @unlink(storage_path('app/'.$job->stored_path));

        $response = $this->actingAs($owner)->get(route('exports.download', $job));

        $response->assertStatus(409)
            ->assertSee('Export artifact is unavailable.')
            ->assertDontSee(storage_path())
            ->assertDontSee($job->stored_path);
        $this->assertDatabaseMissing('audit_logs', ['action' => 'export_csv_downloaded']);
    }

    public function test_corrupt_or_mismatched_artifact_fails_closed_without_audit(): void
    {
        $owner = $this->createAuthorizedUser('download-corrupt@example.invalid');
        $job = $this->completedJob($owner, 'original');
        file_put_contents(storage_path('app/'.$job->stored_path), 'tampered');

        $this->actingAs($owner)->get(route('exports.download', $job))->assertStatus(409);

        $this->assertDatabaseMissing('audit_logs', ['action' => 'export_csv_downloaded']);
    }

    public function test_incomplete_or_traversing_metadata_fails_closed_without_audit(): void
    {
        $owner = $this->createAuthorizedUser('download-invalid-metadata@example.invalid');
        $job = $this->completedJob($owner);
        $job->update([
            'status' => 'pending',
            'stored_path' => '../outside.csv',
            'generated_filename' => '../outside.csv',
        ]);

        $this->actingAs($owner)->get(route('exports.download', $job))->assertStatus(409);

        $this->assertDatabaseMissing('audit_logs', ['action' => 'export_csv_downloaded']);
    }

    public function test_download_permission_seeding_is_idempotent_and_assigns_nothing(): void
    {
        $this->seed(SystemPermissionSeeder::class);
        $this->seed(SystemPermissionSeeder::class);

        $this->assertSame(1, Permission::where('name', 'export.download')->count());
        $this->assertSame('Download verified private exports', Permission::where('name', 'export.download')->value('display_name'));
        $this->assertDatabaseCount('users', 0);
        $this->assertDatabaseCount('roles', 0);
        $this->assertDatabaseCount('role_user', 0);
        $this->assertDatabaseCount('permission_role', 0);
    }

    private function completedJob(User $owner, string $bytes = "column\nsynthetic\n"): ExportJob
    {
        $directory = storage_path('app/exports');
        if (! is_dir($directory)) {
            mkdir($directory, 0777, true);
        }

        $filename = 'download-contract-'.uniqid('', true).'.csv';
        $path = $directory.DIRECTORY_SEPARATOR.$filename;
        file_put_contents($path, $bytes);
        $this->artifacts[] = $path;

        return ExportJob::create([
            'export_type' => 'result_review',
            'status' => 'completed',
            'requested_by_user_id' => $owner->id,
            'filters' => ['source' => 'synthetic_test_only'],
            'stored_path' => 'exports/'.$filename,
            'row_count' => 1,
            'finished_at' => now(),
            'generated_filename' => $filename,
            'mime_type' => 'text/csv',
            'byte_count' => strlen($bytes),
            'sha256' => hash('sha256', $bytes),
        ]);
    }

    private function createAuthorizedUser(string $email): User
    {
        $user = $this->createUser($email);
        $role = Role::create(['name' => 'download-role-'.uniqid()]);
        $permission = Permission::firstOrCreate(['name' => 'export.download']);
        $user->roles()->attach($role);
        $role->permissions()->attach($permission);

        return $user;
    }

    private function createUser(string $email): User
    {
        return User::create([
            'name' => 'EXPORT_DOWNLOAD_TEST_ACCOUNT',
            'email' => $email,
            'password' => 'technical-test-password',
        ]);
    }
}
