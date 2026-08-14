<?php

namespace App\Services\Import;

use App\Models\TargetGroupImportRequest;
use App\Services\Audit\AuditLogger;
use Illuminate\Database\UniqueConstraintViolationException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use LogicException;
use Throwable;

final class TargetGroupImportRequestIdempotencyService
{
    private const CONTEXT_VERSION = 'd8-context-v1';
    private const OPERATION = 'target_group_import';

    public function __construct(private readonly AuditLogger $auditLogger = new AuditLogger())
    {
    }

    /**
     * Register or replay one owned D8-A request without creating job runtime.
     *
     * @param array{import_request_id?:mixed,operation?:mixed,scope_key?:mixed,content_sha256?:mixed,byte_size?:mixed,owner_user_id?:mixed,correlation_id?:mixed} $input
     */
    public function register(array $input): TargetGroupImportRequest
    {
        $normalized = $this->normalize($input);

        try {
            return DB::transaction(function () use ($normalized): TargetGroupImportRequest {
                $existing = TargetGroupImportRequest::query()
                    ->where('import_request_id', $normalized['import_request_id'])
                    ->lockForUpdate()
                    ->first();

                if ($existing !== null) {
                    $this->assertOwner($existing, $normalized['owner_user_id']);

                    if ($existing->operation !== self::OPERATION || $existing->context_fingerprint !== $normalized['context_fingerprint']) {
                        throw new LogicException('IDEMPOTENCY_KEY_CONTEXT_CONFLICT');
                    }

                    $this->auditReplay($existing, $normalized);

                    return $existing->fresh();
                }

                DB::table('import_requests')->insert([
                    'import_request_id' => $normalized['import_request_id'],
                    'operation' => self::OPERATION,
                    'lifecycle_state' => 'PENDING',
                    'context_fingerprint' => $normalized['context_fingerprint'],
                    'correlation_id' => $normalized['correlation_id'],
                    'created_by_user_id' => $normalized['owner_user_id'],
                ]);

                $request = TargetGroupImportRequest::query()
                    ->where('import_request_id', $normalized['import_request_id'])
                    ->firstOrFail();

                $this->auditLogger->log('REQUEST_REGISTERED', 'import_request', null, [
                    'import_request_id' => $request->import_request_id,
                    'correlation_id' => $normalized['correlation_id'],
                    'after_payload' => [
                        'operation' => self::OPERATION,
                        'context_version' => self::CONTEXT_VERSION,
                        'context_fingerprint' => $normalized['context_fingerprint'],
                    ],
                ]);

                return $request->fresh();
            });
        } catch (UniqueConstraintViolationException) {
            return $this->reconcileUniqueCollision($normalized);
        } catch (LogicException $exception) {
            if (in_array($exception->getMessage(), [
                'IDEMPOTENCY_KEY_OWNER_CONFLICT',
                'IDEMPOTENCY_KEY_CONTEXT_CONFLICT',
            ], true)) {
                $this->auditConflict($normalized, $exception->getMessage());
            }

            throw $exception;
        }
    }

    /**
     * @return array{import_request_id:string,owner_user_id:int,correlation_id:string,context_fingerprint:string}
     */
    private function normalize(array $input): array
    {
        if (! array_key_exists('import_request_id', $input) || ! is_string($input['import_request_id']) || preg_match('/\A[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\z/', $input['import_request_id']) !== 1) {
            throw new LogicException('IMPORT_REQUEST_ID_INVALID');
        }

        if (! array_key_exists('operation', $input) || $input['operation'] !== self::OPERATION) {
            throw new LogicException('OPERATION_INVALID');
        }

        if (! array_key_exists('scope_key', $input) || $input['scope_key'] === '') {
            throw new LogicException('SCOPE_KEY_REQUIRED');
        }
        if (! is_string($input['scope_key']) || preg_match('/\A[a-z0-9][a-z0-9._:\/-]{0,127}\z/', $input['scope_key']) !== 1) {
            throw new LogicException('SCOPE_KEY_INVALID');
        }

        if (! array_key_exists('content_sha256', $input) || ! is_string($input['content_sha256']) || preg_match('/\A[a-f0-9]{64}\z/', $input['content_sha256']) !== 1) {
            throw new LogicException('CONTENT_SHA256_INVALID');
        }

        if (! array_key_exists('byte_size', $input) || ! is_int($input['byte_size']) || $input['byte_size'] < 0) {
            throw new LogicException('BYTE_SIZE_INVALID');
        }

        if (! array_key_exists('owner_user_id', $input)) {
            throw new LogicException('REQUEST_OWNER_REQUIRED');
        }
        if (! is_int($input['owner_user_id']) || $input['owner_user_id'] < 1) {
            throw new LogicException('REQUEST_OWNER_INVALID');
        }

        $correlationId = $input['correlation_id'] ?? (string) Str::uuid();
        if (! is_string($correlationId) || Str::isUuid($correlationId) !== true) {
            throw new LogicException('REQUEST_CORRELATION_ID_INVALID');
        }

        $preimage = self::CONTEXT_VERSION."\n"
            .'operation='.self::OPERATION."\n"
            .'scope_key='.$input['scope_key']."\n"
            .'content_sha256='.$input['content_sha256']."\n"
            .'byte_size='.$input['byte_size']."\n";

        return [
            'import_request_id' => $input['import_request_id'],
            'owner_user_id' => $input['owner_user_id'],
            'correlation_id' => $correlationId,
            'context_fingerprint' => hash('sha256', $preimage),
        ];
    }

    private function assertOwner(TargetGroupImportRequest $existing, int $ownerId): void
    {
        if ((int) $existing->created_by_user_id !== $ownerId) {
            throw new LogicException('IDEMPOTENCY_KEY_OWNER_CONFLICT');
        }
    }

    /**
     * @param array{import_request_id:string,owner_user_id:int,correlation_id:string,context_fingerprint:string} $normalized
     */
    private function reconcileUniqueCollision(array $normalized): TargetGroupImportRequest
    {
        try {
            $existing = TargetGroupImportRequest::query()
                ->where('import_request_id', $normalized['import_request_id'])
                ->first();
        } catch (Throwable) {
            $this->auditReconciliation($normalized);
            throw new LogicException('RECONCILIATION_REQUIRED');
        }

        if ($existing === null) {
            $this->auditReconciliation($normalized);
            throw new LogicException('RECONCILIATION_REQUIRED');
        }

        try {
            $this->assertOwner($existing, $normalized['owner_user_id']);
        } catch (LogicException $exception) {
            $this->auditConflict($normalized, $exception->getMessage());
            throw $exception;
        }

        if ($existing->operation !== self::OPERATION || $existing->context_fingerprint !== $normalized['context_fingerprint']) {
            $this->auditConflict($normalized, 'IDEMPOTENCY_KEY_CONTEXT_CONFLICT');
            throw new LogicException('IDEMPOTENCY_KEY_CONTEXT_CONFLICT');
        }

        $this->auditReplay($existing, $normalized, true);

        return $existing->fresh();
    }

    /**
     * @param array{import_request_id:string,owner_user_id:int,correlation_id:string,context_fingerprint:string} $normalized
     */
    private function auditReplay(TargetGroupImportRequest $request, array $normalized, bool $collision = false): void
    {
        $this->auditLogger->log('REQUEST_REPLAYED', 'import_request', null, [
            'import_request_id' => $request->import_request_id,
            'correlation_id' => $normalized['correlation_id'],
            'reconciliation_outcome' => $collision ? 'REUSED' : 'REUSED',
        ]);
    }

    /**
     * @param array{import_request_id:string,owner_user_id:int,correlation_id:string,context_fingerprint:string} $normalized
     */
    private function auditConflict(array $normalized, string $code): void
    {
        $this->auditLogger->log($code, 'import_request', null, [
            'import_request_id' => $normalized['import_request_id'],
            'correlation_id' => $normalized['correlation_id'],
            'conflict_code' => $code,
        ]);
    }

    /**
     * @param array{import_request_id:string,owner_user_id:int,correlation_id:string,context_fingerprint:string} $normalized
     */
    private function auditReconciliation(array $normalized): void
    {
        $this->auditLogger->log('RECONCILIATION_REQUIRED', 'import_request', null, [
            'import_request_id' => $normalized['import_request_id'],
            'correlation_id' => $normalized['correlation_id'],
            'reconciliation_outcome' => 'RECONCILIATION_REQUIRED',
        ]);
    }
}
