<?php

namespace Database\Seeders;

use App\Models\Permission;
use App\Models\Role;
use App\Models\User;
use Illuminate\Database\Console\Seeds\WithoutModelEvents;
use Illuminate\Database\Seeder;

class DatabaseSeeder extends Seeder
{
    use WithoutModelEvents;

    /**
     * Seed the application's database.
     */
    public function run(): void
    {
        // User::factory(10)->create();

        User::factory()->create([
            'name' => 'Test User',
            'email' => 'test@example.com',
        ]);

        $role = Role::firstOrCreate([
            'name' => 'target-group-reviewer',
        ], [
            'display_name' => 'Target-group reviewer',
        ]);

        foreach ([
            'import.targetgroup.review.view',
            'import.targetgroup.identity.view',
            'import.targetgroup.review.approve',
            'import.targetgroup.review.reject',
            'audit.targetgroup.view',
        ] as $permissionName) {
            $permission = Permission::firstOrCreate([
                'name' => $permissionName,
            ], [
                'display_name' => $permissionName,
            ]);

            $role->permissions()->syncWithoutDetaching($permission->id);
        }
    }
}
