<?php

namespace Database\Seeders;

use App\Models\Permission;
use Illuminate\Database\Seeder;

final class SystemPermissionSeeder extends Seeder
{
    public function run(): void
    {
        $permissions = [
            'dashboard.view' => 'View the dashboard',
            'targetgroup.view' => 'View target groups',
            'targetgroup.result.view' => 'View target-group results',
            'targetgroup.result.generate' => 'Generate target-group result drafts',
            'settings.disease.service.view' => 'View disease services',
            'audit.log.view' => 'View global audit logs',
            'import.source.view' => 'View source imports',
            'import.source.preview' => 'Preview source imports',
            'import.source.commit' => 'Commit source imports',
            'import.targetgroup.view' => 'View target-group imports',
            'import.targetgroup.preview' => 'Preview target-group imports',
            'import.targetgroup.commit' => 'Commit target-group imports',
            'export.view' => 'View exports',
            'export.preview' => 'Preview exports',
            'export.generate' => 'Generate deidentified exports',
            'export.download' => 'Download verified private exports',
        ];

        foreach ($permissions as $name => $displayName) {
            Permission::firstOrCreate(
                ['name' => $name],
                ['display_name' => $displayName],
            );
        }
    }
}
