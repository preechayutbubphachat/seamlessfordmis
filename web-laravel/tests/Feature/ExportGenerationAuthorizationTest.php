<?php

namespace Tests\Feature;

use App\Models\Permission;
use App\Models\Role;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Route;
use Tests\TestCase;

final class ExportGenerationAuthorizationTest extends TestCase
{
    use RefreshDatabase;

    protected function tearDown(): void
    {
        $this->removeTestArtifacts();
        parent::tearDown();
    }

    public function test_guest_cannot_generate_and_is_redirected_to_named_login(): void
    {
        $this->post('/exports/generate', [
            'confirmed' => '1',
            'target_group_job_id' => 1,
            'result_generation_job_id' => 1,
        ])->assertRedirect(route('login'));

        $this->assertDatabaseCount('export_jobs', 0);
        $this->assertSame([], $this->exportFiles());
    }

    public function test_authenticated_user_without_permission_receives_forbidden_even_with_permission_input(): void
    {
        $user = $this->createUser('export-trigger-denied@example.invalid');

        $this->actingAs($user)->post('/exports/generate', [
            'confirmed' => '1',
            'target_group_job_id' => 1,
            'result_generation_job_id' => 1,
            'permission' => 'export.generate',
            'role' => 'administrator',
        ])->assertForbidden();

        $this->assertDatabaseCount('export_jobs', 0);
    }

    public function test_generation_form_is_hidden_without_permission_and_visible_with_persisted_permission(): void
    {
        $denied = $this->createUser('export-form-denied@example.invalid');

        $this->actingAs($denied)->get('/exports')
            ->assertOk()
            ->assertDontSee('Generate private deidentified CSV')
            ->assertDontSee('action="'.route('exports.generate').'"', false);

        $allowed = $this->createAuthorizedUser('export-form-allowed@example.invalid');

        $this->actingAs($allowed)->get('/exports')
            ->assertOk()
            ->assertSee('Generate private deidentified CSV')
            ->assertSee('deidentified_internal_v1')
            ->assertSee('contains no CID, name, birth date')
            ->assertSee('review_reason')
            ->assertSee('raw_payload')
            ->assertSee('stores the artifact privately')
            ->assertSee('does not enable download')
            ->assertSee('action="'.route('exports.generate').'"', false)
            ->assertDontSee('requested_by_user_id')
            ->assertDontSee('name="filename"', false)
            ->assertDontSee('name="stored_path"', false)
            ->assertDontSee('name="columns"', false);
    }

    public function test_export_route_contract_has_exactly_six_routes_with_protected_download_and_no_get_generation(): void
    {
        $routes = collect(Route::getRoutes())->filter(
            fn ($route): bool => str_starts_with($route->uri(), 'exports')
        )->values();

        $this->assertCount(6, $routes);
        $this->assertSame([
            ['GET', 'HEAD'],
            ['POST'],
            ['GET', 'HEAD'],
            ['POST'],
            ['POST'],
            ['GET', 'HEAD'],
        ], $routes->sortBy(fn ($route) => match ($route->getName()) {
            'exports.index' => 1,
            'exports.store' => 2,
            'exports.preview' => 3,
            'exports.preview.store' => 4,
            'exports.generate' => 5,
            'exports.download' => 6,
        })->map(fn ($route) => $route->methods())->values()->all());

        $generation = Route::getRoutes()->getByName('exports.generate');
        $this->assertSame('exports/generate', $generation->uri());
        $this->assertSame(['POST'], $generation->methods());
        $this->assertContains('auth', $generation->gatherMiddleware());
        $this->assertContains('permission:export.generate', $generation->gatherMiddleware());
        $this->get('/exports/generate')->assertMethodNotAllowed();

        $download = Route::getRoutes()->getByName('exports.download');
        $this->assertNotNull($download);
        $this->assertSame('exports/{exportJob}/download', $download->uri());
        $this->assertSame(['GET', 'HEAD'], $download->methods());
        $this->assertContains('auth', $download->gatherMiddleware());
        $this->assertContains('permission:export.download', $download->gatherMiddleware());
        $this->assertNull(Route::getRoutes()->getByName('exports.artifact'));
    }

    public function test_existing_post_exports_remains_disabled(): void
    {
        $this->post('/exports', ['export_type' => 'result_review'])
            ->assertStatus(501)
            ->assertJson([
                'message' => 'Export generation is not enabled yet.',
                'file_created' => false,
            ]);

        $this->assertDatabaseHas('export_jobs', ['status' => 'blocked_not_implemented']);
        $this->assertSame([], $this->exportFiles());
    }

    private function createAuthorizedUser(string $email): User
    {
        $user = $this->createUser($email);
        $role = Role::create(['name' => 'export-trigger-role']);
        $permission = Permission::firstOrCreate(['name' => 'export.generate']);
        $user->roles()->attach($role);
        $role->permissions()->attach($permission);

        return $user;
    }

    private function createUser(string $email): User
    {
        return User::create([
            'name' => 'EXPORT_TRIGGER_TEST_ACCOUNT',
            'email' => $email,
            'password' => 'technical-test-password',
        ]);
    }

    private function exportFiles(): array
    {
        return array_values(array_filter(glob(storage_path('app/exports/*')) ?: [], 'is_file'));
    }

    private function removeTestArtifacts(): void
    {
        foreach ($this->exportFiles() as $file) {
            @unlink($file);
        }
        @rmdir(storage_path('app/exports'));
    }
}
