<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

final class ImportSafetyContractTest extends TestCase
{
    use RefreshDatabase;

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
        $this->assertSame(0, DB::table('source_import_jobs')->count());
        $this->assertSame(0, DB::table('source_import_files')->count());
        $this->assertSame(0, DB::table('source_import_rows')->count());
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
