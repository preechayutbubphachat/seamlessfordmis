<?php

namespace Tests\Feature;

use App\Models\Permission;
use App\Models\Role;
use App\Models\User;
use Carbon\Carbon;
use Illuminate\Foundation\Http\Middleware\PreventRequestForgery;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

final class PreviewCommitContractTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutMiddleware(PreventRequestForgery::class);

        $user = User::create([
            'name' => 'SYNTHETIC_PREVIEW_COMMIT',
            'email' => 'synthetic-preview-commit@example.invalid',
            'password' => 'technical-test-password',
        ]);
        $role = Role::create(['name' => 'synthetic-preview-commit-role']);
        $user->roles()->attach($role);
        foreach (['import.source.preview', 'import.source.commit', 'import.targetgroup.preview', 'import.targetgroup.commit'] as $name) {
            $permission = Permission::firstOrCreate(['name' => $name]);
            $role->permissions()->attach($permission);
        }
        $this->actingAs($user);
    }

    protected function tearDown(): void
    {
        Carbon::setTestNow();
        parent::tearDown();
    }

    public function test_source_preview_records_absolute_server_side_expiration_metadata(): void
    {
        Carbon::setTestNow(Carbon::parse('2026-08-18 03:00:00+00:00'));

        $token = $this->previewToken('/imports/source-files/preview', "cid,service_key\n1234567890121,SYN_ALPHA");
        $entry = session('import_previews.'.$token);

        $this->assertSame('2026-08-18T03:00:00+00:00', $entry['created_at']);
        $this->assertSame('2026-08-18T03:30:00+00:00', $entry['expires_at']);
    }

    public function test_source_preview_is_rejected_at_exact_expiration_boundary(): void
    {
        $createdAt = Carbon::parse('2026-08-18 03:00:00+00:00');
        Carbon::setTestNow($createdAt);
        $token = $this->previewToken('/imports/source-files/preview', "cid,service_key\n1234567890121,SYN_ALPHA");

        Carbon::setTestNow($createdAt->copy()->addMinutes(30));

        $this->from('/imports/source-files/preview')->post('/imports/source-files/commit-preview', [
            'preview_token' => $token,
            'import_type' => 'source',
            'confirmed' => '1',
            'expires_at' => '2099-01-01T00:00:00+00:00',
        ])->assertRedirect('/imports/source-files/preview')
            ->assertSessionHasErrors(['preview_token' => 'PREVIEW_EXPIRED']);

        $this->assertSame(0, DB::table('source_import_jobs')->count());
        $this->assertSame(0, DB::table('source_import_files')->count());
        $this->assertSame(0, DB::table('source_import_rows')->count());
        $this->assertSame(0, DB::table('audit_logs')->count());
    }

    public function test_source_preview_is_rejected_after_expiration(): void
    {
        $createdAt = Carbon::parse('2026-08-18 03:00:00+00:00');
        Carbon::setTestNow($createdAt);
        $token = $this->previewToken('/imports/source-files/preview', "cid,service_key\n1234567890121,SYN_ALPHA");

        Carbon::setTestNow($createdAt->copy()->addMinutes(31));

        $this->from('/imports/source-files/preview')->post('/imports/source-files/commit-preview', [
            'preview_token' => $token,
            'import_type' => 'source',
            'confirmed' => '1',
        ])->assertRedirect('/imports/source-files/preview')
            ->assertSessionHasErrors(['preview_token' => 'PREVIEW_EXPIRED']);

        $this->assertSame(0, DB::table('source_import_jobs')->count());
        $this->assertSame(0, DB::table('source_import_files')->count());
        $this->assertSame(0, DB::table('source_import_rows')->count());
        $this->assertSame(0, DB::table('audit_logs')->count());
    }

    public function test_legacy_preview_without_expiration_metadata_fails_closed(): void
    {
        Carbon::setTestNow(Carbon::parse('2026-08-18 03:00:00+00:00'));
        $token = $this->previewToken('/imports/source-files/preview', "cid,service_key\n1234567890121,SYN_ALPHA");
        $entries = session('import_previews');
        unset($entries[$token]['created_at'], $entries[$token]['expires_at']);

        $this->withSession(['import_previews' => $entries])
            ->from('/imports/source-files/preview')->post('/imports/source-files/commit-preview', [
                'preview_token' => $token,
                'import_type' => 'source',
                'confirmed' => '1',
            ])->assertRedirect('/imports/source-files/preview')
                ->assertSessionHasErrors(['preview_token' => 'PREVIEW_EXPIRATION_INVALID']);

        $this->assertSame(0, DB::table('source_import_jobs')->count());
        $this->assertSame(0, DB::table('source_import_files')->count());
        $this->assertSame(0, DB::table('source_import_rows')->count());
        $this->assertSame(0, DB::table('audit_logs')->count());
    }

    public function test_malformed_preview_expiration_metadata_fails_closed(): void
    {
        Carbon::setTestNow(Carbon::parse('2026-08-18 03:00:00+00:00'));
        $token = $this->previewToken('/imports/source-files/preview', "cid,service_key\n1234567890121,SYN_ALPHA");
        $entries = session('import_previews');
        $entries[$token]['expires_at'] = 'not-a-timestamp';

        $this->withSession(['import_previews' => $entries])
            ->from('/imports/source-files/preview')->post('/imports/source-files/commit-preview', [
                'preview_token' => $token,
                'import_type' => 'source',
                'confirmed' => '1',
            ])->assertRedirect('/imports/source-files/preview')
                ->assertSessionHasErrors(['preview_token' => 'PREVIEW_EXPIRATION_INVALID']);

        $this->assertSame('not-a-timestamp', session('import_previews.'.$token.'.expires_at'));
        $this->assertSame(0, DB::table('source_import_jobs')->count());
        $this->assertSame(0, DB::table('source_import_files')->count());
        $this->assertSame(0, DB::table('source_import_rows')->count());
        $this->assertSame(0, DB::table('audit_logs')->count());
    }

    public function test_preview_refresh_does_not_renew_absolute_expiration(): void
    {
        $createdAt = Carbon::parse('2026-08-18 03:00:00+00:00');
        Carbon::setTestNow($createdAt);
        $token = $this->previewToken('/imports/source-files/preview', "cid,service_key\n1234567890121,SYN_ALPHA");
        $expiresAt = session('import_previews.'.$token.'.expires_at');

        $this->get('/imports/source-files/preview')->assertOk();
        $this->assertSame($expiresAt, session('import_previews.'.$token.'.expires_at'));

        Carbon::setTestNow($createdAt->copy()->addMinutes(30));

        $this->from('/imports/source-files/preview')->post('/imports/source-files/commit-preview', [
            'preview_token' => $token,
            'import_type' => 'source',
            'confirmed' => '1',
        ])->assertRedirect('/imports/source-files/preview')
            ->assertSessionHasErrors(['preview_token' => 'PREVIEW_EXPIRED']);

        $this->from('/imports/source-files/preview')->post('/imports/source-files/commit-preview', [
            'preview_token' => $token,
            'import_type' => 'source',
            'confirmed' => '1',
        ])->assertRedirect('/imports/source-files/preview')
            ->assertSessionHasErrors(['preview_token' => 'PREVIEW_EXPIRED']);

        $this->assertSame(0, DB::table('source_import_jobs')->count());
        $this->assertSame(0, DB::table('source_import_files')->count());
        $this->assertSame(0, DB::table('source_import_rows')->count());
        $this->assertSame(0, DB::table('audit_logs')->count());
    }

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
        $createdAt = Carbon::parse('2026-08-18 03:00:00+00:00');
        Carbon::setTestNow($createdAt);
        $token = $this->previewToken('/imports/source-files/preview', "cid,service_key,marker\n1234567890121,SYN_ALPHA,RAW_A");

        Carbon::setTestNow($createdAt->copy()->addMinutes(29));

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

    public function test_confirmed_target_group_preview_is_blocked_without_durable_persistence(): void
    {
        Storage::fake('local');
        $token = $this->previewToken('/imports/target-groups/preview', "cid,full_name,marker\n1234567890129,SYN_INVALID,RAW_B\n,SYN_MISSING,RAW_C");

        $this->from('/imports/target-groups/preview')->post('/imports/target-groups/commit-preview', [
            'preview_token' => $token,
            'import_type' => 'target_group',
            'confirmed' => '1',
        ])->assertRedirect('/imports/target-groups/preview')
            ->assertSessionHasErrors('preview_token');

        $this->assertSame(['TARGET_GROUP_COMMIT_NOT_IMPLEMENTED'], session('errors')->get('preview_token'));
        $this->assertSame(0, DB::table('target_group_jobs')->count());
        $this->assertSame(0, DB::table('target_group_files')->count());
        $this->assertSame(0, DB::table('target_group_rows')->count());
        $this->assertSame(0, DB::table('target_group_history_rows')->count());
        $this->assertSame(0, DB::table('audit_logs')->where('action', 'import_preview_committed')->count());
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

        if (! empty($matches[1])) {
            return $matches[1];
        }

        $tokens = array_keys((array) session('import_previews', []));
        $this->assertNotEmpty($tokens, 'Preview token was not stored in session.');

        return (string) end($tokens);
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
