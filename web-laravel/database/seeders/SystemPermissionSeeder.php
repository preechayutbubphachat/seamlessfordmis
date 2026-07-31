<?php

namespace Database\Seeders;

use App\Models\Permission;
use Illuminate\Database\Seeder;

final class SystemPermissionSeeder extends Seeder
{
    public function run(): void
    {
        Permission::firstOrCreate(
            ['name' => 'export.generate'],
            ['display_name' => 'Generate deidentified exports'],
        );

        Permission::firstOrCreate(
            ['name' => 'export.download'],
            ['display_name' => 'Download verified private exports'],
        );
    }
}
