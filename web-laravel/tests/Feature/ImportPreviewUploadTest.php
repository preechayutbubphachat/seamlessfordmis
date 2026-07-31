<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

final class ImportPreviewUploadTest extends TestCase
{
    use RefreshDatabase;

    public function test_get_preview_forms_return_success(): void
    {
        $this->get('/imports/source-files/preview')
            ->assertOk()
            ->assertSee('Source File CSV Preview')
            ->assertSee('Preview-only');

        $this->get('/imports/target-groups/preview')
            ->assertOk()
            ->assertSee('Target Group CSV Preview')
            ->assertSee('Preview-only');
    }

    public function test_valid_synthetic_source_csv_upload_returns_preview_summary(): void
    {
        Storage::fake('local');

        $response = $this->post('/imports/source-files/preview', [
            'file' => $this->csvFile("cid,service_key\n1234567890121,SYN_ALPHA"),
        ]);

        $response
            ->assertOk()
            ->assertSee('Preview Summary')
            ->assertSee('Total Rows')
            ->assertSee('1')
            ->assertSee('valid')
            ->assertSee('1234567890121')
            ->assertSee('SYN_ALPHA');

        $this->assertNoPreviewSideEffects();
    }

    public function test_target_group_preview_shows_invalid_and_missing_identifier_statuses(): void
    {
        Storage::fake('local');

        $response = $this->post('/imports/target-groups/preview', [
            'file' => $this->csvFile("cid,marker\n1234567890129,SYN_INVALID\n,SYN_MISSING"),
        ]);

        $response
            ->assertOk()
            ->assertSee('invalid_identifier')
            ->assertSee('missing_identifier')
            ->assertSee('SYN_INVALID')
            ->assertSee('SYN_MISSING');

        $this->assertNoPreviewSideEffects();
    }

    public function test_xlsx_upload_is_rejected(): void
    {
        $response = $this->from('/imports/source-files/preview')
            ->post('/imports/source-files/preview', [
                'file' => UploadedFile::fake()->create('synthetic.xlsx', 1, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ]);

        $response
            ->assertRedirect('/imports/source-files/preview')
            ->assertSessionHasErrors('file');
    }

    public function test_oversized_csv_upload_is_rejected(): void
    {
        $response = $this->from('/imports/target-groups/preview')
            ->post('/imports/target-groups/preview', [
                'file' => UploadedFile::fake()->create('synthetic.csv', 1025, 'text/csv'),
            ]);

        $response
            ->assertRedirect('/imports/target-groups/preview')
            ->assertSessionHasErrors('file');
    }

    public function test_post_preview_does_not_insert_staging_result_or_export_rows(): void
    {
        Storage::fake('local');

        $before = $this->tableCounts();

        $this->post('/imports/source-files/preview', [
            'file' => $this->csvFile("cid,service_key\n1234567890121,SYN_ALPHA"),
        ])->assertOk();

        $this->assertSame($before, $this->tableCounts());
        $this->assertNoPreviewSideEffects();
    }

    public function test_import_commit_routes_remain_blocked(): void
    {
        Storage::fake('local');

        $this->post('/imports/source-files', [
            'file' => UploadedFile::fake()->create('blocked.txt', 1, 'text/plain'),
        ])->assertStatus(501);

        $this->post('/imports/target-groups', [
            'file' => UploadedFile::fake()->create('blocked.txt', 1, 'text/plain'),
        ])->assertStatus(501);

        Storage::disk('local')->assertMissing('blocked.txt');
        Storage::disk('local')->assertMissing('imports/blocked.txt');
    }

    private function csvFile(string $content): UploadedFile
    {
        return UploadedFile::fake()->createWithContent('synthetic.csv', $content);
    }

    private function tableCounts(): array
    {
        return [
            'source_import_jobs' => DB::table('source_import_jobs')->count(),
            'source_import_files' => DB::table('source_import_files')->count(),
            'source_import_rows' => DB::table('source_import_rows')->count(),
            'target_group_jobs' => DB::table('target_group_jobs')->count(),
            'target_group_files' => DB::table('target_group_files')->count(),
            'target_group_rows' => DB::table('target_group_rows')->count(),
            'result_generation_jobs' => DB::table('result_generation_jobs')->count(),
            'target_group_results' => DB::table('target_group_results')->count(),
            'target_group_result_sources' => DB::table('target_group_result_sources')->count(),
            'export_jobs' => DB::table('export_jobs')->count(),
        ];
    }

    private function assertNoPreviewSideEffects(): void
    {
        Storage::disk('local')->assertMissing('imports/synthetic.csv');
        Storage::disk('local')->assertMissing('imports/synthetic.xlsx');
        Storage::disk('local')->assertMissing('exports/synthetic.csv');
        Storage::disk('local')->assertMissing('exports/synthetic.xlsx');
    }
}
