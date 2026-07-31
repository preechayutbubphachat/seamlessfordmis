<?php

namespace Tests\Unit;

use App\Services\FileHashService;
use PHPUnit\Framework\TestCase;

final class FileHashServiceTest extends TestCase
{
    private array $tempFiles = [];

    protected function tearDown(): void
    {
        foreach ($this->tempFiles as $path) {
            if (is_file($path)) {
                unlink($path);
            } elseif (is_dir($path)) {
                rmdir($path);
            }
        }
    }

    public function test_same_synthetic_content_with_different_filename_has_same_sha256(): void
    {
        $first = $this->tempFile('alpha.txt', "synthetic\ncontent\n");
        $second = $this->tempFile('beta.txt', "synthetic\ncontent\n");
        $service = new FileHashService();

        $this->assertSame($service->sha256($first), $service->sha256($second));
    }

    public function test_different_synthetic_content_has_different_sha256(): void
    {
        $first = $this->tempFile('first.txt', "synthetic one\n");
        $second = $this->tempFile('second.txt', "synthetic two\n");
        $service = new FileHashService();

        $this->assertNotSame($service->sha256($first), $service->sha256($second));
    }

    public function test_hash_does_not_include_path_or_mtime(): void
    {
        $first = $this->tempFile('mtime-a.txt', "same content\n");
        $second = $this->tempFile('mtime-b.txt', "same content\n");
        touch($first, 1700000000);
        touch($second, 1800000000);
        $service = new FileHashService();

        $this->assertSame($service->sha256($first), $service->sha256($second));
    }

    private function tempFile(string $name, string $content): string
    {
        $dir = sys_get_temp_dir() . DIRECTORY_SEPARATOR . 'seamlessfordmis-tests-' . bin2hex(random_bytes(4));
        mkdir($dir);
        $path = $dir . DIRECTORY_SEPARATOR . $name;
        file_put_contents($path, $content);
        $this->tempFiles[] = $path;
        $this->tempFiles[] = $dir;

        return $path;
    }
}
