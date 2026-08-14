<?php

namespace Tests\Feature;

use App\Models\AuditLog;
use App\Models\TargetGroupImportRequest;
use App\Services\Import\TargetGroupImportRequestIdempotencyService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use LogicException;
use Tests\TestCase;

final class TargetGroupImportRequestIdempotencyTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        DB::table('users')->insert([
            'id' => 17,
            'name' => 'Synthetic D8 Owner',
            'email' => 'synthetic-d8-owner@example.test',
            'password' => password_hash('synthetic-test-only', PASSWORD_BCRYPT),
        ]);
    }

    public function test_canonical_uuidv4_is_accepted_and_context_serialization_is_exact(): void
    {
        $input = $this->input();
        $request = $this->service()->register($input);
        $preimage = "d8-context-v1\noperation=target_group_import\nscope_key=synthetic.scope\ncontent_sha256={$input['content_sha256']}\nbyte_size=12\n";

        $this->assertSame(hash('sha256', $preimage), $request->context_fingerprint);
        $this->assertSame($input['import_request_id'], $request->getKey());
        $this->assertStringEndsWith("byte_size=12\n", $preimage);
        $this->assertNotSame(hash('sha256', rtrim($preimage, "\n")), $request->context_fingerprint);
        $audit = AuditLog::query()->where('action', 'REQUEST_REGISTERED')->sole();
        $this->assertSame($input['import_request_id'], $audit->import_request_id);
        $this->assertNull($audit->entity_id);
    }

    public function test_uuidv1_v3_v5_uppercase_braced_whitespace_and_malformed_keys_are_rejected(): void
    {
        foreach ([
            '11111111-1111-1111-8111-111111111111',
            '11111111-1111-3111-8111-111111111111',
            '11111111-1111-5111-8111-111111111111',
            '11111111-1111-4111-8111-11111111111A',
            '{11111111-1111-4111-8111-111111111111}',
            ' 11111111-1111-4111-8111-111111111111',
            '11111111111141118111111111111111',
            'not-a-uuid',
        ] as $key) {
            $input = $this->input(['import_request_id' => $key]);
            $this->assertCode('IMPORT_REQUEST_ID_INVALID', fn () => $this->service()->register($input));
        }
        $this->assertSame(0, TargetGroupImportRequest::query()->count());
    }

    public function test_scope_operation_sha_size_and_owner_validation_are_strict(): void
    {
        $cases = [
            ['scope_key' => '', 'code' => 'SCOPE_KEY_REQUIRED'],
            ['scope_key' => 'BadScope', 'code' => 'SCOPE_KEY_INVALID'],
            ['scope_key' => 'synthetic scope', 'code' => 'SCOPE_KEY_INVALID'],
            ['scope_key' => 'synthetic/สcope', 'code' => 'SCOPE_KEY_INVALID'],
            ['operation' => 'TARGET_GROUP_IMPORT', 'code' => 'OPERATION_INVALID'],
            ['content_sha256' => strtoupper(hash('sha256', 'SYN_REQUEST')), 'code' => 'CONTENT_SHA256_INVALID'],
            ['content_sha256' => str_repeat('g', 64), 'code' => 'CONTENT_SHA256_INVALID'],
            ['byte_size' => -1, 'code' => 'BYTE_SIZE_INVALID'],
            ['byte_size' => '12', 'code' => 'BYTE_SIZE_INVALID'],
            ['owner_user_id' => 0, 'code' => 'REQUEST_OWNER_INVALID'],
            ['owner_user_id' => '12', 'code' => 'REQUEST_OWNER_INVALID'],
        ];

        foreach ($cases as $case) {
            $code = $case['code'];
            unset($case['code']);
            $this->assertCode($code, fn () => $this->service()->register($this->input($case)));
        }
        $missingOwner = $this->input();
        unset($missingOwner['owner_user_id']);
        $this->assertCode('REQUEST_OWNER_REQUIRED', fn () => $this->service()->register($missingOwner));
    }

    public function test_fresh_request_registers_once_with_typed_uuid_audit_and_no_job_runtime(): void
    {
        $input = $this->input();
        $request = $this->service()->register($input);

        $this->assertSame(1, TargetGroupImportRequest::query()->count());
        $this->assertSame($input['owner_user_id'], $request->created_by_user_id);
        $this->assertSame('PENDING', $request->lifecycle_state);
        $audit = AuditLog::query()->where('action', 'REQUEST_REGISTERED')->sole();
        $this->assertSame($input['import_request_id'], $audit->import_request_id);
        $this->assertNull($audit->entity_id);
        $this->assertStringNotContainsString($input['import_request_id'], json_encode($audit->before_payload));
        $this->assertStringNotContainsString($input['import_request_id'], json_encode($audit->after_payload));
        $this->assertSame(0, DB::table('target_group_jobs')->count());
        $this->assertSame(0, DB::table('target_group_job_attempts')->count());
        $this->assertSame(0, DB::table('target_group_file_versions')->count());
        $this->assertSame(0, DB::table('target_group_history_rows')->count());
    }

    public function test_same_key_same_owner_same_context_replays_exact_request(): void
    {
        $input = $this->input();
        $first = $this->service()->register($input);
        $second = $this->service()->register($input);

        $this->assertSame($first->getKey(), $second->getKey());
        $this->assertSame(1, TargetGroupImportRequest::query()->count());
        $this->assertSame(1, AuditLog::query()->where('action', 'REQUEST_REGISTERED')->count());
        $replay = AuditLog::query()->where('action', 'REQUEST_REPLAYED')->sole();
        $this->assertSame($input['import_request_id'], $replay->import_request_id);
        $this->assertSame('REUSED', $replay->reconciliation_outcome);
    }

    public function test_owner_conflict_is_fail_closed_and_does_not_reveal_context(): void
    {
        $input = $this->input(['owner_user_id' => 17]);
        $this->service()->register($input);
        $conflict = $this->input(['owner_user_id' => 202, 'scope_key' => 'secret.scope', 'content_sha256' => hash('sha256', 'SECRET_CONTEXT')]);

        $this->assertCode('IDEMPOTENCY_KEY_OWNER_CONFLICT', fn () => $this->service()->register($conflict));

        $audit = AuditLog::query()->where('action', 'IDEMPOTENCY_KEY_OWNER_CONFLICT')->sole();
        $this->assertSame($input['import_request_id'], $audit->import_request_id);
        $this->assertSame('IDEMPOTENCY_KEY_OWNER_CONFLICT', $audit->conflict_code);
        $this->assertStringNotContainsString('secret.scope', (string) $audit->before_payload);
        $this->assertStringNotContainsString('SECRET_CONTEXT', (string) $audit->after_payload);
        $this->assertSame(1, TargetGroupImportRequest::query()->count());
    }

    public function test_same_owner_context_conflicts_are_fail_closed_for_scope_sha_size_and_operation(): void
    {
        $input = $this->input();
        $this->service()->register($input);

        foreach ([
            ['scope_key' => 'synthetic.other'],
            ['content_sha256' => hash('sha256', 'SYN_OTHER_SHA')],
            ['byte_size' => 13],
        ] as $change) {
            $this->assertCode('IDEMPOTENCY_KEY_CONTEXT_CONFLICT', fn () => $this->service()->register($this->input($change)));
        }

        DB::table('import_requests')->where('import_request_id', $input['import_request_id'])->update(['operation' => 'other_operation']);
        $this->assertCode('IDEMPOTENCY_KEY_CONTEXT_CONFLICT', fn () => $this->service()->register($input));
        $this->assertSame(4, AuditLog::query()->where('action', 'IDEMPOTENCY_KEY_CONTEXT_CONFLICT')->count());
        $this->assertSame(1, TargetGroupImportRequest::query()->count());
    }

    public function test_conflicts_do_not_create_second_request_job_attempt_version_or_history(): void
    {
        $input = $this->input();
        $this->service()->register($input);
        $this->assertCode('IDEMPOTENCY_KEY_CONTEXT_CONFLICT', fn () => $this->service()->register($this->input(['scope_key' => 'synthetic.conflict'])));

        $this->assertSame(1, TargetGroupImportRequest::query()->count());
        $this->assertSame(0, DB::table('target_group_jobs')->count());
        $this->assertSame(0, DB::table('target_group_job_attempts')->count());
        $this->assertSame(0, DB::table('target_group_file_versions')->count());
        $this->assertSame(0, DB::table('target_group_history_rows')->count());
    }

    public function test_request_typed_audit_does_not_coerce_uuid_into_entity_id_and_legacy_logger_survives(): void
    {
        $input = $this->input();
        $this->service()->register($input);
        $audit = AuditLog::query()->where('action', 'REQUEST_REGISTERED')->sole();
        $this->assertSame($input['import_request_id'], $audit->import_request_id);
        $this->assertNull($audit->entity_id);

        $logger = new \App\Services\Audit\AuditLogger();
        $logger->log('SYN_LEGACY_UUID_COMPAT', 'synthetic', 456, ['after_payload' => ['safe' => true]]);
        $legacy = AuditLog::query()->where('action', 'SYN_LEGACY_UUID_COMPAT')->sole();
        $this->assertSame(456, $legacy->entity_id);
        $this->assertTrue($legacy->after_payload['safe']);
    }

    public function test_unknown_authoritative_state_is_not_silently_replaced(): void
    {
        $input = $this->input();
        DB::table('import_requests')->insert([
            'import_request_id' => $input['import_request_id'],
            'operation' => 'target_group_import',
            'lifecycle_state' => 'PENDING',
            'context_fingerprint' => str_repeat('f', 64),
            'correlation_id' => '11111111-1111-4111-8111-111111111111',
            'created_by_user_id' => $input['owner_user_id'],
        ]);

        $this->assertCode('IDEMPOTENCY_KEY_CONTEXT_CONFLICT', fn () => $this->service()->register($input));
        $this->assertSame(1, TargetGroupImportRequest::query()->count());
    }

    private function service(): TargetGroupImportRequestIdempotencyService
    {
        return new TargetGroupImportRequestIdempotencyService();
    }

    private function input(array $overrides = []): array
    {
        return array_merge([
            'import_request_id' => '11111111-1111-4111-8111-111111111111',
            'operation' => 'target_group_import',
            'scope_key' => 'synthetic.scope',
            'content_sha256' => hash('sha256', 'SYN_REQUEST'),
            'byte_size' => 12,
            'owner_user_id' => 17,
        ], $overrides);
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
