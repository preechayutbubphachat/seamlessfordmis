<?php

namespace Tests\Feature;

use App\Models\Permission;
use App\Models\Role;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Route;
use Tests\TestCase;

final class PermissionMiddlewareTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        Route::middleware(['web', 'auth', 'permission:export.generate'])
            ->get('/_test/permission/export-generate', fn () => response('allowed'));
        Route::middleware(['web', 'auth', 'permission'])
            ->get('/_test/permission/missing-argument', fn () => response('must-not-run'));
    }

    public function test_guest_is_handled_by_auth_middleware(): void
    {
        $this->get('/_test/permission/export-generate')
            ->assertRedirect(route('login'));

        $this->getJson('/_test/permission/export-generate')
            ->assertUnauthorized();
    }

    public function test_authenticated_user_without_permission_receives_controlled_forbidden(): void
    {
        $this->actingAs($this->createUser())
            ->get('/_test/permission/export-generate')
            ->assertForbidden()
            ->assertSee('This action is not authorized.');
    }

    public function test_authenticated_user_with_persisted_permission_is_allowed(): void
    {
        $user = $this->createUser();
        $role = Role::create(['name' => 'export-operator']);
        $permission = Permission::create(['name' => 'export.generate']);
        $user->roles()->attach($role);
        $role->permissions()->attach($permission);

        $this->actingAs($user)
            ->get('/_test/permission/export-generate')
            ->assertOk()
            ->assertSee('allowed');
    }

    public function test_missing_argument_and_request_input_fail_closed(): void
    {
        $user = $this->createUser();

        $this->actingAs($user)
            ->get('/_test/permission/missing-argument?permission=export.generate&role=admin')
            ->assertForbidden();

        $this->actingAs($user)
            ->get('/_test/permission/export-generate?permission=export.generate&role=admin')
            ->assertForbidden();
    }

    private function createUser(): User
    {
        return User::create([
            'name' => 'AUTH_MIDDLEWARE_ACCOUNT',
            'email' => 'auth-middleware@example.invalid',
            'password' => 'technical-test-password',
        ]);
    }
}
