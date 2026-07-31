<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

final class PreviewCommitContractTest extends TestCase
{
    use RefreshDatabase;

    public function test_preview_with_errors_cannot_commit(): void
    {
        $token = hash('sha256', 'synthetic-error-preview');

        $this->withSession([
            'import_previews' => [
                $token => [
                    'import_type' => 'source',
                    'preview' => [
                        'total_rows' => 0,
                        'valid_rows' => 0,
                        'invalid_rows' => 0,
                        'missing_identifier_rows' => 0,
                        'errors' => [['code' => 'missing_required_columns']],
                        'warnings' => [],
                        'rows' => [],
                    ],
                    'sha256' => hash('sha256', 'synthetic-error-content'),
                    'original_filename' => 'synthetic.csv',
                ],
            ],
        ])->from('/imports/source-files/preview')->post('/imports/source-files/commit-preview', [
            'preview_token' => $token,
            'import_type' => 'source',
            'confirmed' => '1',
        ])->assertRedirect('/imports/source-files/preview')
            ->assertSessionHasErrors('preview_token');

        $this->assertSame(0, DB::table('source_import_rows')->count());
        $this->assertSame(0, DB::table('audit_logs')->count());
    }

    public function test_commit_without_confirmation_is_rejected(): void
    {
        $token = $this->previewToken('/imports/source-files/preview', "cid,service_key\n1234567890121,SYN_ALPHA");

        $this->from('/imports/source-files/preview')->post('/imports/source-files/commit-preview', [
            'preview_token' => $token,
            'import_type' => 'source',
        ])->assertRedirect('/imports/source-files/preview')
            ->assertSessionHasErrors('confirmed');

        $this->assertSame(0, DB::table('source_import_rows')->count());
        $this->assertSame(0, DB::table('audit_logs')->count());
    }

    public function test_confirmed_source_preview_commits_staging_rows_and_audit_log(): void
    {
        Storage::fake('local');
        $token = $this->previewToken('/imports/source-files/preview', "cid,service_key,marker\n1234567890121,SYN_ALPHA,RAW_A");

        $this->post('/imports/source-files/commit-preview', [
            'preview_token' => $token,
            'import_type' => 'source',
            'confirmed' => '1',
        ])->assertRedirect();

        $this->assertSame(1, DB::table('source_import_jobs')->count());
        $this->assertSame(1, DB::table('source_import_files')->count());
        $this->assertSame(1, DB::table('source_import_rows')->count());
        $this->assertDatabaseHas('source_import_rows', [
            'row_number' => 2,
            'raw_cid' => '1234567890121',
            'normalized_cid' => '1234567890121',
            'cid_status' => 'valid',
            'validation_status' => 'valid',
        ]);
        $this->assertDatabaseHas('audit_logs', [
            'action' => 'import_preview_committed',
            'entity_type' => 'source_import_job',
        ]);
        $this->assertNoResultExportOrStorageSideEffects();
    }

    public function test_confirmed_target_group_preview_commits_staging_rows_and_preserves_invalid_missing_statuses(): void
    {
        Storage::fake('local');
        $token = $this->previewToken('/imports/target-groups/preview', "cid,full_name,marker\n1234567890129,SYN_INVALID,RAW_B\n,SYN_MISSING,RAW_C");

        $this->post('/imports/target-groups/commit-preview', [
            'preview_token' => $token,
            'import_type' => 'target_group',
            'confirmed' => '1',
        ])->assertRedirect();

        $this->assertSame(1, DB::table('target_group_jobs')->count());
        $this->assertSame(1, DB::table('target_group_files')->count());
        $this->assertSame(2, DB::table('target_group_rows')->count());
        $this->assertDatabaseHas('target_group_rows', [
            'row_number' => 2,
            'raw_cid' => '1234567890129',
            'cid_status' => 'invalid_identifier',
            'validation_status' => 'invalid_identifier',
        ]);
        $this->assertDatabaseHas('target_group_rows', [
            'row_number' => 3,
            'raw_cid' => '',
            'cid_status' => 'missing_identifier',
            'validation_status' => 'missing_identifier',
        ]);
        $this->assertDatabaseHas('audit_logs', [
            'action' => 'import_preview_committed',
            'entity_type' => 'target_group_job',
        ]);
        $this->assertNoResultExportOrStorageSideEffects();
    }

    public function test_duplicate_source_commit_is_blocked_by_content_sha256(): void
    {
        $content = "cid,service_key\n1234567890121,SYN_ALPHA";
        $firstToken = $this->previewToken('/imports/source-files/preview', $content);

        $this->post('/imports/source-files/commit-preview', [
            'preview_token' => $firstToken,
            'import_type' => 'source',
            'confirmed' => '1',
        ])->assertRedirect();

        $secondToken = $this->previewToken('/imports/source-files/preview', $content);

        $this->from('/imports/source-files/preview')->post('/imports/source-files/commit-preview', [
            'preview_token' => $secondToken,
            'import_type' => 'source',
            'confirmed' => '1',
        ])->assertRedirect('/imports/source-files/preview')
            ->assertSessionHasErrors('preview_token');

        $this->assertSame(1, DB::table('source_import_jobs')->count());
        $this->assertSame(1, DB::table('source_import_files')->count());
        $this->assertSame(1, DB::table('source_import_rows')->count());
        $this->assertSame(1, DB::table('audit_logs')->count());
    }

    public function test_post_preview_route_remains_preview_only_and_commit_routes_are_separate(): void
    {
        Storage::fake('local');

        $this->post('/imports/source-files/preview', [
            'file' => $this->csvFile("cid,service_key\n1234567890121,SYN_ALPHA"),
        ])->assertOk();

        $this->assertSame(0, DB::table('source_import_rows')->count());
        $this->assertSame(0, DB::table('audit_logs')->count());
        $this->assertNoResultExportOrStorageSideEffects();
    }

    private function previewToken(string $path, string $content): string
    {
        $response = $this->post($path, [
            'file' => $this->csvFile($content),
        ])->assertOk();

        $html = $response->getContent();
        preg_match('/name="preview_token" value="([a-f0-9]{64})"/', $html, $matches);

        $this->assertNotEmpty($matches[1] ?? null, 'Preview token was not rendered.');

        return $matches[1];
    }

    private function csvFile(string $content): UploadedFile
    {
        return UploadedFile::fake()->createWithContent('synthetic.csv', $content);
    }

    private function assertNoResultExportOrStorageSideEffects(): void
    {
        $this->assertSame(0, DB::table('result_generation_jobs')->count());
        $this->assertSame(0, DB::table('target_group_results')->count());
        $this->assertSame(0, DB::table('target_group_result_sources')->count());
        $this->assertSame(0, DB::table('export_jobs')->count());
        Storage::disk('local')->assertMissing('imports/synthetic.csv');
        Storage::disk('local')->assertMissing('exports/synthetic.csv');
        Storage::disk('local')->assertMissing('exports/synthetic.xlsx');
    }
}
