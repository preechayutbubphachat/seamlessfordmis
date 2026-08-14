<?php

namespace Tests\Feature;

use App\Models\AuditLog;
use App\Models\ImportContentObject;
use App\Services\Import\ImportContentObjectRegistrationService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use LogicException;
use Tests\TestCase;

final class ImportContentObjectRegistrationTest extends TestCase
{
    use RefreshDatabase;

    public function test_valid_sha_and_size_register_once_with_typed_audit(): void
    {
        $sha = hash('sha256', 'SYN_CONTENT_REGISTER');
        $content = $this->service()->register(['sha256' => $sha, 'byte_size' => 20]);

        $this->assertSame($sha, $content->sha256);
        $this->assertSame(20, $content->byte_size);
        $this->assertSame(1, ImportContentObject::query()->count());
        $audit = AuditLog::query()->where('action', 'CONTENT_REGISTERED')->sole();
        $this->assertSame($content->getKey(), $audit->content_object_id);
        $this->assertNull($audit->entity_id);
        $this->assertNull($audit->import_request_id);
        $this->assertSame([], array_intersect(['raw_payload', 'patient', 'cid', 'hn'], array_keys($audit->after_payload ?? [])));
    }

    public function test_same_sha_and_same_size_reuses_authoritative_content_and_audits_reuse(): void
    {
        $sha = hash('sha256', 'SYN_CONTENT_REUSE');
        $first = $this->service()->register(['sha256' => $sha, 'byte_size' => 18]);
        $second = $this->service()->register(['sha256' => $sha, 'byte_size' => 18]);

        $this->assertSame($first->getKey(), $second->getKey());
        $this->assertSame(1, ImportContentObject::query()->count());
        $audit = AuditLog::query()->where('action', 'CONTENT_REUSED')->sole();
        $this->assertSame($first->getKey(), $audit->content_object_id);
        $this->assertSame('REUSED', $audit->reconciliation_outcome);
    }

    public function test_same_sha_and_different_size_fails_closed_without_overwrite(): void
    {
        $sha = hash('sha256', 'SYN_CONTENT_CONFLICT');
        $first = $this->service()->register(['sha256' => $sha, 'byte_size' => 19]);

        $this->assertCode('CONTENT_HASH_METADATA_CONFLICT', fn () => $this->service()->register(['sha256' => $sha, 'byte_size' => 20]));

        $this->assertSame(19, DB::table('import_content_objects')->where('id', $first->getKey())->value('byte_size'));
        $this->assertSame(1, ImportContentObject::query()->count());
        $audit = AuditLog::query()->where('action', 'CONTENT_HASH_METADATA_CONFLICT')->sole();
        $this->assertSame('CONTENT_HASH_METADATA_CONFLICT', $audit->conflict_code);
        $this->assertSame('RECONCILIATION_REQUIRED', $audit->reconciliation_outcome);
    }

    public function test_invalid_uppercase_missing_nonhex_and_negative_values_fail_closed(): void
    {
        foreach ([
            ['sha256' => strtoupper(hash('sha256', 'SYN_UPPER')), 'byte_size' => 4],
            ['sha256' => str_repeat('g', 64), 'byte_size' => 4],
            ['byte_size' => 4],
        ] as $input) {
            $this->assertCode('CONTENT_SHA256_INVALID', fn () => $this->service()->register($input));
        }

        $this->assertCode('CONTENT_BYTE_SIZE_INVALID', fn () => $this->service()->register([
            'sha256' => hash('sha256', 'SYN_NEGATIVE'),
            'byte_size' => -1,
        ]));
        $this->assertSame(0, ImportContentObject::query()->count());
    }

    public function test_zero_byte_content_is_deterministic_and_reusable(): void
    {
        $sha = hash('sha256', '');
        $first = $this->service()->register(['sha256' => $sha, 'byte_size' => 0]);
        $second = $this->service()->register(['sha256' => $sha, 'byte_size' => 0]);

        $this->assertSame($first->getKey(), $second->getKey());
        $this->assertSame(0, $second->byte_size);
    }

    public function test_authoritative_existing_content_readback_returns_the_winner(): void
    {
        $sha = hash('sha256', 'SYN_CONTENT_WINNER');
        $winnerId = DB::table('import_content_objects')->insertGetId(['sha256' => $sha, 'byte_size' => 21]);

        $result = $this->service()->register(['sha256' => $sha, 'byte_size' => 21]);

        $this->assertSame($winnerId, $result->getKey());
        $this->assertSame(1, ImportContentObject::query()->count());
        $this->assertSame($winnerId, AuditLog::query()->where('action', 'CONTENT_REUSED')->sole()->content_object_id);
    }

    public function test_content_registration_has_no_request_job_attempt_version_or_history_side_effects(): void
    {
        $this->service()->register(['sha256' => hash('sha256', 'SYN_SIDE_EFFECT_FREE'), 'byte_size' => 22]);

        $this->assertSame(0, DB::table('import_requests')->count());
        $this->assertSame(0, DB::table('target_group_jobs')->count());
        $this->assertSame(0, DB::table('target_group_job_attempts')->count());
        $this->assertSame(0, DB::table('target_group_file_versions')->count());
        $this->assertSame(0, DB::table('target_group_history_rows')->count());
    }

    public function test_existing_audit_logger_legacy_entity_id_usage_remains_operational(): void
    {
        $logger = new \App\Services\Audit\AuditLogger();
        $logger->log('SYN_LEGACY_AUDIT', 'synthetic', 123, ['after_payload' => ['safe' => 'value']]);

        $audit = AuditLog::query()->where('action', 'SYN_LEGACY_AUDIT')->sole();
        $this->assertSame(123, $audit->entity_id);
        $this->assertSame('value', $audit->after_payload['safe']);
    }

    private function service(): ImportContentObjectRegistrationService
    {
        return new ImportContentObjectRegistrationService();
    }

    private function assertCode(string $code, callable $operation): void
    {
        try {
            $operation();
            $this->fail("Expected {$code}.");
        } catch (LogicException $exception) {
            $this->assertSame($code, $exception->getMessage());
        }
    }
}
