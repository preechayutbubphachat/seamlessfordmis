<?php

namespace Tests\Unit;

use App\Services\Import\CsvPreviewParser;
use App\Services\Import\ImportPreviewService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

final class CsvPreviewParserTest extends TestCase
{
    use RefreshDatabase;

    public function test_valid_synthetic_csv_preview_returns_preview_counts(): void
    {
        $preview = (new CsvPreviewParser())->parseString(
            "cid,service_key,service_date,status\n1234567890121,SYN_ALPHA,2026-01-01,observed",
            ['cid', 'service_key']
        );

        $this->assertSame(1, $preview['total_rows']);
        $this->assertSame(1, $preview['valid_rows']);
        $this->assertSame(0, $preview['invalid_rows']);
        $this->assertSame(0, $preview['missing_identifier_rows']);
        $this->assertSame([], $preview['errors']);
        $this->assertSame('valid', $preview['rows'][0]['identifier_status']);
        $this->assertSame('1234567890121', $preview['rows'][0]['normalized_cid']);
    }

    public function test_missing_required_columns_fail_without_rows(): void
    {
        $preview = (new CsvPreviewParser())->parseString(
            "cid,status\n1234567890121,observed",
            ['cid', 'service_key']
        );

        $this->assertSame(0, $preview['total_rows']);
        $this->assertSame([], $preview['rows']);
        $this->assertSame('missing_required_columns', $preview['errors'][0]['code']);
        $this->assertSame(['service_key'], $preview['errors'][0]['columns']);
    }

    public function test_invalid_cid_is_invalid_identifier_not_no_history(): void
    {
        $preview = (new CsvPreviewParser())->parseString(
            "cid,service_key\n1234567890129,SYN_ALPHA"
        );

        $this->assertSame(1, $preview['invalid_rows']);
        $this->assertSame('invalid_identifier', $preview['rows'][0]['identifier_status']);
        $this->assertNotSame('no_history', $preview['rows'][0]['validation_status']);
    }

    public function test_missing_cid_is_missing_identifier_not_no_history(): void
    {
        $preview = (new CsvPreviewParser())->parseString(
            "cid,service_key\n,SYN_ALPHA"
        );

        $this->assertSame(1, $preview['missing_identifier_rows']);
        $this->assertSame('missing_identifier', $preview['rows'][0]['identifier_status']);
        $this->assertNotSame('no_history', $preview['rows'][0]['validation_status']);
    }

    public function test_raw_payload_and_row_number_are_preserved(): void
    {
        $preview = (new CsvPreviewParser())->parseString(
            "cid,service_key,marker\n1234567890121,SYN_ALPHA,RAW_A\n1234567890129,SYN_BETA,RAW_B"
        );

        $this->assertSame(2, $preview['rows'][0]['row_number']);
        $this->assertSame(3, $preview['rows'][1]['row_number']);
        $this->assertSame([
            'cid' => '1234567890129',
            'service_key' => 'SYN_BETA',
            'marker' => 'RAW_B',
        ], $preview['rows'][1]['raw_payload']);
    }

    public function test_parser_does_not_write_database_store_file_or_generate_outputs(): void
    {
        Storage::fake('local');

        $before = [
            'source_import_rows' => DB::table('source_import_rows')->count(),
            'target_group_results' => DB::table('target_group_results')->count(),
            'export_jobs' => DB::table('export_jobs')->count(),
        ];

        (new CsvPreviewParser())->parseString(
            "cid,service_key\n1234567890121,SYN_ALPHA"
        );

        $this->assertSame($before['source_import_rows'], DB::table('source_import_rows')->count());
        $this->assertSame($before['target_group_results'], DB::table('target_group_results')->count());
        $this->assertSame($before['export_jobs'], DB::table('export_jobs')->count());
        Storage::disk('local')->assertMissing('imports/synthetic.csv');
        Storage::disk('local')->assertMissing('exports/synthetic.csv');
        Storage::disk('local')->assertMissing('exports/synthetic.xlsx');
    }

    public function test_preview_service_reads_synthetic_temp_file_outside_repo(): void
    {
        $path = tempnam(sys_get_temp_dir(), 'w8_preview_');
        $this->assertIsString($path);

        try {
            file_put_contents($path, "cid,service_key\n1234567890121,SYN_ALPHA");

            $preview = (new ImportPreviewService())->previewCsvFile($path, ['cid', 'service_key']);

            $this->assertSame(1, $preview['total_rows']);
            $this->assertSame('valid', $preview['rows'][0]['identifier_status']);
        } finally {
            if (is_file($path)) {
                unlink($path);
            }
        }
    }

    public function test_confirmed_target_group_alias_maps_without_enabling_proposed_aliases(): void
    {
        $preview = (new CsvPreviewParser())->parseString(
            "cid,name,ชื่อ\n1234567890121,SYN_NAME,SYN_PROPOSED_ALIAS",
            ['cid', 'full_name'],
            'target_group',
        );

        $this->assertSame('full_name', $preview['header_mapping']['name']);
        $this->assertArrayNotHasKey('ชื่อ', array_filter($preview['header_mapping']));
        $this->assertNull($preview['header_mapping']['ชื่อ']);
        $this->assertSame(1, $preview['valid_rows']);
        $this->assertSame('SYN_PROPOSED_ALIAS', $preview['rows'][0]['raw_payload']['ชื่อ']);
    }

    public function test_proposed_full_name_validation_rule_is_not_enforced_by_preview(): void
    {
        $preview = (new CsvPreviewParser())->parseString(
            "cid,full_name\n1234567890121,",
            ['cid', 'full_name'],
            'target_group',
        );

        $this->assertSame(1, $preview['valid_rows']);
        $this->assertSame([], $preview['errors']);
        $this->assertSame('', $preview['rows'][0]['raw_payload']['full_name']);
    }

    public function test_duplicate_recognized_header_is_a_blocking_preview_error(): void
    {
        $preview = (new CsvPreviewParser())->parseString(
            "cid,full_name,name\n1234567890121,SYN_NAME,SYN_DUPLICATE",
            ['cid', 'full_name'],
            'target_group',
        );

        $this->assertSame(0, $preview['total_rows']);
        $this->assertSame('duplicate_recognized_header', $preview['errors'][0]['code']);
        $this->assertSame(['full_name'], $preview['errors'][0]['columns']);
    }

    public function test_streaming_csv_preview_preserves_quoted_delimiters_escaped_quotes_multiline_and_utf8(): void
    {
        $preview = (new CsvPreviewParser())->parseString(
            "cid,full_name,marker\n1234567890121,\"บุคคล, \\\"ตัวอย่าง\\\"\nบรรทัดสอง\",SYN_MARKER",
            ['cid', 'full_name'],
            'target_group',
        );

        $this->assertSame(1, $preview['total_rows']);
        $this->assertSame(1, $preview['valid_rows']);
        $this->assertSame(2, $preview['rows'][0]['row_number']);
        $this->assertSame("บุคคล, \\\"ตัวอย่าง\\\"\nบรรทัดสอง", $preview['rows'][0]['raw_payload']['full_name']);
        $this->assertSame('SYN_MARKER', $preview['rows'][0]['raw_payload']['marker']);
    }

    public function test_empty_and_header_only_csv_are_read_only_previews(): void
    {
        $empty = (new CsvPreviewParser())->parseString('', ['cid'], 'target_group');
        $headerOnly = (new CsvPreviewParser())->parseString("cid,full_name\n", ['cid', 'full_name'], 'target_group');

        $this->assertSame('missing_header', $empty['errors'][0]['code']);
        $this->assertSame(0, $headerOnly['total_rows']);
        $this->assertSame([], $headerOnly['errors']);
        $this->assertSame([], $headerOnly['rows']);
    }
}
