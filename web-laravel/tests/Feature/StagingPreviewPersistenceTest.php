<?php

namespace Tests\Feature;

use App\Services\Import\CsvPreviewParser;
use App\Services\Import\StagingImportService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use LogicException;
use Tests\TestCase;

final class StagingPreviewPersistenceTest extends TestCase
{
    use RefreshDatabase;

    public function test_persist_source_preview_creates_job_file_and_rows(): void
    {
        $preview = $this->preview("cid,service_key,service_date\n1234567890121,SYN_ALPHA,2026-01-01");

        $result = (new StagingImportService())->persistSourcePreview($preview, [
            'job_name' => 'Synthetic source staging',
            'sheet_name' => 'synthetic-sheet',
        ]);

        $this->assertSame('preview_staged', $result['status']);
        $this->assertSame(1, DB::table('source_import_jobs')->count());
        $this->assertSame(1, DB::table('source_import_files')->count());
        $this->assertSame(1, DB::table('source_import_rows')->count());
        $this->assertDatabaseHas('source_import_rows', [
            'source_import_job_id' => $result['source_import_job_id'],
            'source_file_id' => $result['source_file_id'],
            'row_number' => 2,
            'raw_cid' => '1234567890121',
            'normalized_cid' => '1234567890121',
            'cid_status' => 'valid',
            'validation_status' => 'valid',
        ]);
    }

    public function test_persist_target_group_preview_creates_job_file_and_rows(): void
    {
        $preview = $this->preview("cid,full_name,birth_date\n1234567890121,SYN_NAME,2026-01-01");

        $result = (new StagingImportService())->persistTargetGroupPreview($preview, [
            'group_name' => 'Synthetic target group staging',
            'sheet_name' => 'synthetic-sheet',
        ]);

        $this->assertSame('preview_staged', $result['status']);
        $this->assertSame(1, DB::table('target_group_jobs')->count());
        $this->assertSame(1, DB::table('target_group_files')->count());
        $this->assertSame(1, DB::table('target_group_rows')->count());
        $this->assertDatabaseHas('target_group_rows', [
            'target_group_job_id' => $result['target_group_job_id'],
            'target_group_file_id' => $result['target_group_file_id'],
            'row_number' => 2,
            'raw_cid' => '1234567890121',
            'normalized_cid' => '1234567890121',
            'cid_status' => 'valid',
            'validation_status' => 'valid',
        ]);
    }

    public function test_raw_payload_and_invalid_missing_statuses_are_preserved(): void
    {
        $preview = $this->preview("cid,service_key,marker\n1234567890129,SYN_ALPHA,RAW_A\n,SYN_BETA,RAW_B");

        (new StagingImportService())->persistSourcePreview($preview);

        $invalid = DB::table('source_import_rows')->where('row_number', 2)->first();
        $missing = DB::table('source_import_rows')->where('row_number', 3)->first();

        $this->assertSame('invalid_identifier', $invalid->cid_status);
        $this->assertSame('invalid_identifier', $invalid->validation_status);
        $this->assertSame('RAW_A', json_decode($invalid->raw_payload, true)['marker']);
        $this->assertSame('missing_identifier', $missing->cid_status);
        $this->assertSame('missing_identifier', $missing->validation_status);
        $this->assertSame('RAW_B', json_decode($missing->raw_payload, true)['marker']);
    }

    public function test_malformed_preview_rolls_back_source_staging(): void
    {
        $this->expectException(LogicException::class);
        $this->expectExceptionMessage('Malformed preview row is missing row_number.');

        $preview = $this->preview("cid,service_key\n1234567890121,SYN_ALPHA");
        unset($preview['rows'][0]['row_number']);

        try {
            (new StagingImportService())->persistSourcePreview($preview);
        } finally {
            $this->assertSame(0, DB::table('source_import_jobs')->count());
            $this->assertSame(0, DB::table('source_import_files')->count());
            $this->assertSame(0, DB::table('source_import_rows')->count());
        }
    }

    public function test_staging_preview_does_not_create_results_or_storage_files(): void
    {
        Storage::fake('local');

        $preview = $this->preview("cid,service_key\n1234567890121,SYN_ALPHA");

        (new StagingImportService())->persistTargetGroupPreview($preview);

        $this->assertSame(0, DB::table('result_generation_jobs')->count());
        $this->assertSame(0, DB::table('target_group_results')->count());
        $this->assertSame(0, DB::table('target_group_result_sources')->count());
        Storage::disk('local')->assertMissing('imports/synthetic-preview.csv');
        Storage::disk('local')->assertMissing('exports/synthetic-preview.csv');
        Storage::disk('local')->assertMissing('exports/synthetic-preview.xlsx');
    }

    public function test_retry_same_source_preview_is_blocked_without_duplicate_rows(): void
    {
        $this->expectException(LogicException::class);
        $this->expectExceptionMessage('Synthetic source preview was already staged.');

        $service = new StagingImportService();
        $preview = $this->preview("cid,service_key\n1234567890121,SYN_ALPHA");

        $service->persistSourcePreview($preview, ['job_name' => 'Retry synthetic source']);

        try {
            $service->persistSourcePreview($preview, ['job_name' => 'Retry synthetic source']);
        } finally {
            $this->assertSame(1, DB::table('source_import_jobs')->count());
            $this->assertSame(1, DB::table('source_import_files')->count());
            $this->assertSame(1, DB::table('source_import_rows')->count());
        }
    }

    private function preview(string $csv): array
    {
        return (new CsvPreviewParser())->parseString($csv);
    }
}
