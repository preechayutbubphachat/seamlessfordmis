<?php

namespace Tests\Unit;

use App\Services\Export\ExportCsvWriter;
use PHPUnit\Framework\TestCase;
use RuntimeException;

final class ExportCsvWriterTest extends TestCase
{
    private string $directory;

    protected function setUp(): void
    {
        parent::setUp();
        $this->directory = sys_get_temp_dir().DIRECTORY_SEPARATOR.'w12-writer-'.bin2hex(random_bytes(6));
    }

    protected function tearDown(): void
    {
        if (is_dir($this->directory)) {
            foreach (glob($this->directory.DIRECTORY_SEPARATOR.'*') ?: [] as $file) {
                @unlink($file);
            }
            @rmdir($this->directory);
        }
        parent::tearDown();
    }

    public function test_writer_uses_bom_crlf_final_newline_and_standard_csv_escaping(): void
    {
        $path = $this->directory.DIRECTORY_SEPARATOR.'artifact.csv';
        $metadata = (new ExportCsvWriter)->write($path, ['first', 'second'], [
            ['comma,value', 'quote"value'],
            ["line\nbreak", 'plain'],
        ]);
        $bytes = file_get_contents($path);

        $this->assertStringStartsWith(ExportCsvWriter::UTF8_BOM, $bytes);
        $this->assertSame(1, substr_count($bytes, ExportCsvWriter::UTF8_BOM));
        $this->assertStringContainsString('"comma,value","quote""value"', $bytes);
        $this->assertStringContainsString('"line'."\n".'break",plain', $bytes);
        $this->assertDoesNotMatchRegularExpression('/(?<!\r)\n/', str_replace("line\nbreak", 'line-break', $bytes));
        $this->assertStringEndsWith("\r\n", $bytes);
        $this->assertSame(2, $metadata['row_count']);
        $this->assertSame(strlen($bytes), $metadata['byte_count']);
        $this->assertSame(hash('sha256', $bytes), $metadata['sha256']);
    }

    public function test_every_parsed_row_has_the_header_column_count(): void
    {
        $path = $this->directory.DIRECTORY_SEPARATOR.'artifact.csv';
        (new ExportCsvWriter)->write($path, ['a', 'b'], [['1', '2'], ['3', '4']]);
        $handle = fopen($path, 'rb');
        fread($handle, 3);
        $rows = [];
        while (($row = fgetcsv($handle, escape: '')) !== false) {
            $rows[] = $row;
        }
        fclose($handle);

        $this->assertCount(3, $rows);
        foreach ($rows as $row) {
            $this->assertCount(2, $row);
        }
    }

    public function test_column_mismatch_removes_temporary_and_final_files(): void
    {
        $path = $this->directory.DIRECTORY_SEPARATOR.'artifact.csv';

        try {
            (new ExportCsvWriter)->write($path, ['a', 'b'], [['only-one']]);
            $this->fail('Column mismatch must fail.');
        } catch (RuntimeException $exception) {
            $this->assertSame('export_row_column_count_mismatch', $exception->getMessage());
        }

        $this->assertFileDoesNotExist($path);
        $this->assertSame([], glob($this->directory.DIRECTORY_SEPARATOR.'*.tmp-*') ?: []);
    }

    public function test_existing_artifact_is_never_overwritten(): void
    {
        mkdir($this->directory, 0700, true);
        $path = $this->directory.DIRECTORY_SEPARATOR.'artifact.csv';
        file_put_contents($path, 'unrelated-artifact');

        $this->expectException(RuntimeException::class);
        $this->expectExceptionMessage('export_artifact_already_exists');

        try {
            (new ExportCsvWriter)->write($path, ['a'], [['b']]);
        } finally {
            $this->assertSame('unrelated-artifact', file_get_contents($path));
        }
    }
}
