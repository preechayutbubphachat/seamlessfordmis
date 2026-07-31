<?php

namespace Tests\Unit;

use App\Services\CidValidator;
use PHPUnit\Framework\TestCase;

final class CidValidatorTest extends TestCase
{
    public function test_validates_synthetic_cid_with_correct_check_digit(): void
    {
        $result = (new CidValidator())->validate('1234567890121');

        $this->assertTrue($result['is_valid']);
        $this->assertSame('valid', $result['status']);
        $this->assertSame('1234567890121', $result['normalized_cid']);
    }

    public function test_rejects_synthetic_cid_with_invalid_check_digit(): void
    {
        $result = (new CidValidator())->validate('1234567890129');

        $this->assertFalse($result['is_valid']);
        $this->assertSame('invalid_identifier', $result['status']);
        $this->assertSame('1234567890129', $result['normalized_cid']);
    }

    public function test_rejects_non_13_digit_value(): void
    {
        $result = (new CidValidator())->validate('123456789012');

        $this->assertFalse($result['is_valid']);
        $this->assertSame('invalid_identifier', $result['status']);
        $this->assertNull($result['normalized_cid']);
    }

    public function test_reports_missing_value(): void
    {
        $result = (new CidValidator())->validate('  ');

        $this->assertFalse($result['is_valid']);
        $this->assertSame('missing_identifier', $result['status']);
        $this->assertNull($result['normalized_cid']);
    }

    public function test_rejects_non_numeric_value(): void
    {
        $result = (new CidValidator())->validate('12345678901A1');

        $this->assertFalse($result['is_valid']);
        $this->assertSame('invalid_identifier', $result['status']);
        $this->assertNull($result['normalized_cid']);
    }
}
