<?php

namespace Tests\Feature;

use App\Services\Import\CsvPreviewParser;
use App\Services\Import\StagingImportService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

final class StagingImportReviewUiTest extends TestCase
{
    use RefreshDatabase;

    private function csvFile(string $content): UploadedFile
    {
        return UploadedFile::fake()->createWithContent('synthetic.csv', $content);
    }

    public function test_source_import_list_returns_success_with_empty_state(): void
    {
        $this->get('/imports/source-files')
            ->assertOk()
            ->assertSee('Source Files')
            ->assertSee('No staging imports yet')
            ->assertSee('No real patient data')
            ->assertSee('No upload form is available');
    }

    public function test_source_import_detail_empty_and_with_synthetic_rows_returns_success(): void
    {
        $this->get('/imports/source-files/999')
            ->assertOk()
            ->assertSee('Source Import Job Detail')
            ->assertSee('No staged rows yet');

        $result = (new StagingImportService())->persistSourcePreview(
            (new CsvPreviewParser())->parseString("cid,service_key,service_date,marker\n1234567890121,SYN_ALPHA,2026-01-01,RAW_A")
        );

        $this->get('/imports/source-files/'.$result['source_import_job_id'])
            ->assertOk()
            ->assertSee('Source Import Job Detail')
            ->assertSee('preview_staged')
            ->assertSee('1234567890121')
            ->assertSee('valid')
            ->assertSee('SYN_ALPHA')
            ->assertSee('RAW_A')
            ->assertDontSee('Commit')
            ->assertDontSee('Delete');
    }

    public function test_target_group_list_returns_success_with_empty_state(): void
    {
        $this->get('/imports/target-groups')
            ->assertOk()
            ->assertSee('Target Group Imports')
            ->assertSee('No staging imports yet')
            ->assertSee('No real patient data')
            ->assertSee('No upload form is available');
    }

    public function test_target_group_detail_empty_and_with_synthetic_rows_returns_success(): void
    {
        $this->get('/imports/target-groups/999')
            ->assertOk()
            ->assertSee('Target Group Import Job Detail')
            ->assertSee('No staged rows yet');

        $result = (new StagingImportService())->persistTargetGroupPreview(
            (new CsvPreviewParser())->parseString("cid,full_name,birth_date,marker\n1234567890121,SYN_NAME,2026-01-01,RAW_B")
        );

        $this->get('/imports/target-groups/'.$result['target_group_job_id'])
            ->assertOk()
            ->assertSee('Target Group Import Job Detail')
            ->assertSee('preview_staged')
            ->assertSee('1234567890121')
            ->assertSee('valid')
            ->assertSee('SYN_NAME')
            ->assertSee('RAW_B')
            ->assertDontSee('Commit')
            ->assertDontSee('Delete');
    }

    public function test_source_import_post_uses_functional_import_contract(): void
    {
        Storage::fake('local');

        // Valid source import should be accepted and staged
        $response = $this->post('/imports/source-files', [
            'files' => [
                $this->csvFile("cid,service_key\n1234567890121,SYN_ALPHA"),
            ],
        ]);

        $response
            ->assertOk()
            ->assertJsonStructure([
                'message',
                'source_import_job_id',
                'source_file_ids',
                'sha256',
                'rows_inserted',
                'status',
                'reconciliation',
                'file_stored',
                'patient_data_imported',
            ])
            ->assertJson([
                'message' => 'Source import completed successfully.',
                'file_stored' => true,
                'patient_data_imported' => false,
                'status' => 'completed',
            ]);

        $this->assertDatabaseCount('source_import_jobs', 1);
        $this->assertDatabaseCount('source_import_files', 1);
        $this->assertDatabaseCount('source_import_rows', 1);

        // Target groups route still returns 501 (not implemented in this slice)
        $this->post('/imports/target-groups', [
            'files' => [
                $this->csvFile("cid,marker\n1234567890121,SYN_ALPHA"),
            ],
        ])->assertStatus(501);

        Storage::disk('local')->assertMissing('blocked.txt');
        Storage::disk('local')->assertMissing('imports/blocked.txt');
    }

    public function test_source_import_post_rejects_invalid_request_without_persistence(): void
    {
        Storage::fake('local');

        // Old 'file' key (not 'files' array) should be rejected with 302 redirect + session errors
        $response = $this->post('/imports/source-files', [
            'file' => $this->csvFile("cid,service_key\n1234567890121,SYN_ALPHA"),
        ]);

        $response->assertStatus(302);
        $response->assertSessionHasErrors('files');

        $this->assertDatabaseCount('source_import_jobs', 0);
        $this->assertDatabaseCount('source_import_files', 0);
        $this->assertDatabaseCount('source_import_rows', 0);

        Storage::disk('local')->assertMissing('blocked.txt');
        Storage::disk('local')->assertMissing('imports/blocked.txt');
    }

    public function test_get_review_pages_do_not_write_database_or_storage(): void
    {
        Storage::fake('local');

        $before = $this->tableCounts();

        $this->get('/imports/source-files')->assertOk();
        $this->get('/imports/source-files/1')->assertOk();
        $this->get('/imports/target-groups')->assertOk();
        $this->get('/imports/target-groups/1')->assertOk();

        $this->assertSame($before, $this->tableCounts());
        Storage::disk('local')->assertMissing('imports/synthetic-preview.csv');
        Storage::disk('local')->assertMissing('exports/synthetic-preview.csv');
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
            'export_jobs' => DB::table('export_jobs')->count(),
        ];
    }
}
