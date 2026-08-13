<?php

namespace Tests\Feature;

use App\Models\Permission;
use App\Models\Role;
use App\Models\User;
use Illuminate\Foundation\Http\Middleware\PreventRequestForgery;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class AdminPlaceholderRoutesTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutMiddleware(PreventRequestForgery::class);

        $user = User::create([
            'name' => 'SYNTHETIC_ADMIN_PLACEHOLDER',
            'email' => 'synthetic-admin-placeholder@example.invalid',
            'password' => 'technical-test-password',
        ]);
        $role = Role::create(['name' => 'synthetic-admin-placeholder-role']);
        $user->roles()->attach($role);
        $permission = Permission::firstOrCreate(['name' => 'dashboard.view']);
        $role->permissions()->attach($permission);
        $this->actingAs($user);
    }

    public function test_root_redirects_to_dashboard_placeholder(): void
    {
        $this->get('/')->assertRedirect('/dashboard');

        $this->get('/dashboard')
            ->assertOk()
            ->assertSee('Dashboard')
            ->assertSee('No real patient data');
    }
}
