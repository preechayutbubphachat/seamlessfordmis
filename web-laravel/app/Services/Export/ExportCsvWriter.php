<?php

namespace App\Services\Export;

use RuntimeException;
use Throwable;

class ExportCsvWriter
{
    public const UTF8_BOM = "\xEF\xBB\xBF";

    public const MIME_TYPE = 'text/csv';

    public const LINE_ENDING = "\r\n";

    public function write(string $finalPath, array $header, iterable $rows): array
    {
        $directory = dirname($finalPath);
        if (! is_dir($directory) && ! mkdir($directory, 0700, true) && ! is_dir($directory)) {
            throw new RuntimeException('private_export_directory_creation_failed');
        }

        if (is_file($finalPath)) {
            throw new RuntimeException('export_artifact_already_exists');
        }

        $temporaryPath = $finalPath.'.tmp-'.bin2hex(random_bytes(8));
        $handle = null;
        $rowCount = 0;

        try {
            $handle = fopen($temporaryPath, 'xb');
            if ($handle === false) {
                throw new RuntimeException('export_temporary_file_open_failed');
            }

            $this->writeBytes($handle, self::UTF8_BOM);
            $this->writeCsvRow($handle, $header);

            foreach ($rows as $row) {
                if (count($row) !== count($header)) {
                    throw new RuntimeException('export_row_column_count_mismatch');
                }

                $this->writeCsvRow($handle, $row);
                $rowCount++;
            }

            if (! fflush($handle)) {
                throw new RuntimeException('export_file_flush_failed');
            }

            fclose($handle);
            $handle = null;

            if (! rename($temporaryPath, $finalPath)) {
                throw new RuntimeException('export_atomic_rename_failed');
            }

            $byteCount = filesize($finalPath);
            $sha256 = hash_file('sha256', $finalPath);
            if ($byteCount === false || $sha256 === false) {
                throw new RuntimeException('export_artifact_measurement_failed');
            }

            return [
                'row_count' => $rowCount,
                'byte_count' => $byteCount,
                'sha256' => $sha256,
                'mime_type' => self::MIME_TYPE,
            ];
        } catch (Throwable $exception) {
            if (is_resource($handle)) {
                fclose($handle);
            }

            if (is_file($temporaryPath)) {
                @unlink($temporaryPath);
            }

            if (is_file($finalPath)) {
                @unlink($finalPath);
            }

            throw $exception;
        }
    }

    private function writeCsvRow($handle, array $row): void
    {
        if (fputcsv($handle, $row, ',', '"', '', self::LINE_ENDING) === false) {
            throw new RuntimeException('export_csv_write_failed');
        }
    }

    private function writeBytes($handle, string $bytes): void
    {
        if (fwrite($handle, $bytes) !== strlen($bytes)) {
            throw new RuntimeException('export_csv_write_failed');
        }
    }
}
