<?php

namespace App\Services;

use InvalidArgumentException;
use RuntimeException;

final class FileHashService
{
    public function sha256(string $path): string
    {
        if (!is_file($path)) {
            throw new InvalidArgumentException('Hash source must be a file.');
        }

        if (!is_readable($path)) {
            throw new RuntimeException('Hash source is not readable.');
        }

        $hash = hash_file('sha256', $path);

        if ($hash === false) {
            throw new RuntimeException('Unable to calculate SHA256 hash.');
        }

        return $hash;
    }
}
