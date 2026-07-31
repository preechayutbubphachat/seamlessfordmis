<?php

namespace Tests\Feature;

use App\Services\Export\ExportService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use LogicException;
use Tests\TestCase;

final class ExportSkeletonContractTest extends TestCase
{
    use RefreshDatabase;

    public function test_exports_page_returns_success(): void
    {
        $this->get('/exports')
            ->assertOk()
            ->assertSee('Exports')
            ->assertSee('Export generation is not enabled yet');
    }

    public function test_empty_exports_page_shows_no_export_jobs(): void
    {
        $this->get('/exports')
            ->assertOk()
            ->assertSee('No export jobs yet');
    }

    public function test_exports_page_lists_blocked_export_jobs(): void
    {
        DB::table('export_jobs')->insert([
            'export_type' => 'result_review',
            'status' => 'blocked_not_implemented',
            'filters' => json_encode(['synthetic_filter' => 'stored_results_only']),
            'error_message' => 'Export generation is not enabled yet.',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $this->get('/exports')
            ->assertOk()
            ->assertSee('result_review')
            ->assertSee('blocked_not_implemented')
            ->assertSee('stored_results_only')
            ->assertDontSee('Download');
    }

    public function test_export_post_creates_blocked_job_without_creating_export_file(): void
    {
        Storage::fake('local');

        $response = $this->post('/exports', [
            'export_type' => 'result_review',
        ]);

        $response
            ->assertStatus(501)
            ->assertJson([
                'message' => 'Export generation is not enabled yet.',
                'file_created' => false,
            ]);

        $this->assertSame(1, DB::table('export_jobs')->count());
        $this->assertDatabaseHas('export_jobs', [
            'export_type' => 'result_review',
            'status' => 'blocked_not_implemented',
            'stored_path' => null,
        ]);
        Storage::disk('local')->assertMissing('exports/result_review.csv');
        Storage::disk('local')->assertMissing('exports/result_review.xlsx');
    }

    public function test_export_service_refuses_to_generate_fake_output(): void
    {
        $this->expectException(LogicException::class);
        $this->expectExceptionMessage('Export generation is not enabled yet.');

        (new ExportService())->generateFileFromStoredResults('result_review', []);
    }
}
