<?php

namespace Tests\Feature;

use App\Models\Permission;
use Database\Seeders\SystemPermissionSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class SystemPermissionSeederTest extends TestCase
{
    use RefreshDatabase;

    public function test_seeder_registers_export_permission_idempotently_without_users_roles_or_assignments(): void
    {
        $unrelated = Permission::create([
            'name' => 'technical.unrelated',
            'display_name' => 'UNCHANGED_TECHNICAL_LABEL',
        ]);

        $this->seed(SystemPermissionSeeder::class);
        $this->seed(SystemPermissionSeeder::class);

        $this->assertSame(1, Permission::where('name', 'export.generate')->count());
        $this->assertSame('Generate deidentified exports', Permission::where('name', 'export.generate')->value('display_name'));
        $this->assertSame(1, Permission::where('name', 'export.download')->count());
        $this->assertSame('Download verified private exports', Permission::where('name', 'export.download')->value('display_name'));
        $this->assertSame('UNCHANGED_TECHNICAL_LABEL', $unrelated->fresh()->display_name);
        $this->assertDatabaseCount('permissions', 17);
        $this->assertDatabaseCount('users', 0);
        $this->assertDatabaseCount('roles', 0);
        $this->assertDatabaseCount('role_user', 0);
        $this->assertDatabaseCount('permission_role', 0);
    }
}
