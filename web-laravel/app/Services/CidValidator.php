<?php

namespace App\Services;

final class CidValidator
{
    public const STATUS_VALID = 'valid';
    public const STATUS_MISSING = 'missing_identifier';
    public const STATUS_INVALID = 'invalid_identifier';

    /**
     * @return array{is_valid: bool, status: string, normalized_cid: ?string}
     */
    public function validate(?string $rawCid): array
    {
        $candidate = trim((string) $rawCid);

        if ($candidate === '') {
            return $this->result(false, self::STATUS_MISSING, null);
        }

        if (!preg_match('/^\d{13}$/', $candidate)) {
            return $this->result(false, self::STATUS_INVALID, null);
        }

        if (!$this->hasValidCheckDigit($candidate)) {
            return $this->result(false, self::STATUS_INVALID, $candidate);
        }

        return $this->result(true, self::STATUS_VALID, $candidate);
    }

    private function hasValidCheckDigit(string $cid): bool
    {
        $sum = 0;

        for ($index = 0; $index < 12; $index++) {
            $sum += ((int) $cid[$index]) * (13 - $index);
        }

        $expected = (11 - ($sum % 11)) % 10;

        return $expected === (int) $cid[12];
    }

    /**
     * @return array{is_valid: bool, status: string, normalized_cid: ?string}
     */
    private function result(bool $isValid, string $status, ?string $normalizedCid): array
    {
        return [
            'is_valid' => $isValid,
            'status' => $status,
            'normalized_cid' => $normalizedCid,
        ];
    }
}
