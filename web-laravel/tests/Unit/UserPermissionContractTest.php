<?php

namespace Tests\Unit;

use App\Models\Permission;
use App\Models\Role;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class UserPermissionContractTest extends TestCase
{
    use RefreshDatabase;

    public function test_bidirectional_role_and_permission_relationships_work(): void
    {
        $user = $this->createUser();
        $role = Role::create(['name' => 'export-operator']);
        $permission = Permission::create(['name' => 'export.generate']);

        $user->roles()->attach($role);
        $role->permissions()->attach($permission);

        $this->assertTrue($user->roles->contains($role));
        $this->assertTrue($role->users->contains($user));
        $this->assertTrue($role->permissions->contains($permission));
        $this->assertTrue($permission->roles->contains($role));
        $this->assertTrue($user->hasPermission('export.generate'));
    }

    public function test_permission_check_fails_closed_for_missing_unknown_and_noncanonical_values(): void
    {
        $user = $this->createUser();
        $role = Role::create(['name' => 'technical-role']);
        $permission = Permission::create(['name' => 'export.generate']);
        $user->roles()->attach($role);

        $this->assertFalse($user->hasPermission('export.generate'));

        $role->permissions()->attach($permission);

        foreach (['', 'unknown.permission', 'EXPORT.GENERATE', 'export', 'export.*', 'export.gen', ' export.generate', 'export.generate '] as $candidate) {
            $this->assertFalse($user->hasPermission($candidate), $candidate);
        }
    }

    public function test_unrelated_role_does_not_grant_and_duplicate_attach_does_not_duplicate_effect(): void
    {
        $user = $this->createUser();
        $assignedRole = Role::create(['name' => 'assigned-role']);
        $unrelatedRole = Role::create(['name' => 'unrelated-role']);
        $permission = Permission::create(['name' => 'export.generate']);
        $unrelatedRole->permissions()->attach($permission);
        $user->roles()->syncWithoutDetaching([$assignedRole->id]);
        $user->roles()->syncWithoutDetaching([$assignedRole->id]);

        $this->assertFalse($user->hasPermission('export.generate'));
        $this->assertDatabaseCount('role_user', 1);

        $assignedRole->permissions()->syncWithoutDetaching([$permission->id]);
        $assignedRole->permissions()->syncWithoutDetaching([$permission->id]);

        $this->assertTrue($user->hasPermission('export.generate'));
        $this->assertDatabaseCount('permission_role', 2);
    }

    private function createUser(): User
    {
        return User::create([
            'name' => 'AUTH_TEST_ACCOUNT',
            'email' => 'auth-test@example.invalid',
            'password' => 'technical-test-password',
        ]);
    }
}
