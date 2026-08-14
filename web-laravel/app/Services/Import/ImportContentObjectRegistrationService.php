<?php

namespace App\Services\Import;

use App\Models\ImportContentObject;
use App\Services\Audit\AuditLogger;
use Illuminate\Database\UniqueConstraintViolationException;
use Illuminate\Support\Facades\DB;
use LogicException;
use Throwable;

final class ImportContentObjectRegistrationService
{
    public function __construct(private readonly AuditLogger $auditLogger = new AuditLogger())
    {
    }

    /**
     * Register or reuse exact byte evidence without creating import runtime state.
     *
     * @param array{sha256?:mixed,byte_size?:mixed,correlation_id?:mixed} $input
     */
    public function register(array $input): ImportContentObject
    {
        $normalized = $this->normalize($input);

        try {
            return DB::transaction(function () use ($normalized): ImportContentObject {
                $existing = ImportContentObject::query()
                    ->where('sha256', $normalized['sha256'])
                    ->lockForUpdate()
                    ->first();

                if ($existing !== null) {
                    if ((int) $existing->byte_size !== $normalized['byte_size']) {
                        throw new LogicException('CONTENT_HASH_METADATA_CONFLICT');
                    }

                    $this->audit('CONTENT_REUSED', $existing, $normalized, 'REUSED');

                    return $existing->fresh();
                }

                $content = ImportContentObject::query()->create([
                    'sha256' => $normalized['sha256'],
                    'byte_size' => $normalized['byte_size'],
                ]);

                $this->audit('CONTENT_REGISTERED', $content, $normalized);

                return $content->fresh();
            });
        } catch (UniqueConstraintViolationException) {
            return $this->reconcileUniqueCollision($normalized);
        } catch (LogicException $exception) {
            if ($exception->getMessage() === 'CONTENT_HASH_METADATA_CONFLICT') {
                $existing = $this->readContent($normalized['sha256']);
                $this->auditConflict($existing, $normalized);
            }

            throw $exception;
        }
    }

    /**
     * @return array{sha256:string,byte_size:int,correlation_id:?string}
     */
    private function normalize(array $input): array
    {
        if (! array_key_exists('sha256', $input) || ! is_string($input['sha256']) || preg_match('/\A[a-f0-9]{64}\z/', $input['sha256']) !== 1) {
            throw new LogicException('CONTENT_SHA256_INVALID');
        }

        if (! array_key_exists('byte_size', $input) || ! is_int($input['byte_size']) || $input['byte_size'] < 0) {
            throw new LogicException('CONTENT_BYTE_SIZE_INVALID');
        }

        $correlationId = $input['correlation_id'] ?? null;
        if ($correlationId !== null && (! is_string($correlationId) || $correlationId === '')) {
            throw new LogicException('CONTENT_CORRELATION_ID_INVALID');
        }

        return [
            'sha256' => $input['sha256'],
            'byte_size' => $input['byte_size'],
            'correlation_id' => $correlationId,
        ];
    }

    /**
     * @param array{sha256:string,byte_size:int,correlation_id:?string} $normalized
     */
    private function reconcileUniqueCollision(array $normalized): ImportContentObject
    {
        try {
            $existing = $this->readContent($normalized['sha256']);
        } catch (Throwable) {
            throw new LogicException('RECONCILIATION_REQUIRED');
        }

        if ($existing === null) {
            throw new LogicException('RECONCILIATION_REQUIRED');
        }

        if ((int) $existing->byte_size !== $normalized['byte_size']) {
            $this->auditConflict($existing, $normalized);
            throw new LogicException('CONTENT_HASH_METADATA_CONFLICT');
        }

        $this->audit('CONTENT_COLLISION_RECONCILED', $existing, $normalized, 'REUSED');

        return $existing->fresh();
    }

    private function readContent(string $sha256): ?ImportContentObject
    {
        return ImportContentObject::query()->where('sha256', $sha256)->first();
    }

    /**
     * @param array{sha256:string,byte_size:int,correlation_id:?string} $normalized
     */
    private function audit(string $action, ImportContentObject $content, array $normalized, ?string $outcome = null): void
    {
        $context = [
            'content_object_id' => (int) $content->getKey(),
            'correlation_id' => $normalized['correlation_id'],
            'after_payload' => [
                'sha256' => $normalized['sha256'],
                'byte_size' => $normalized['byte_size'],
            ],
        ];
        if ($outcome !== null) {
            $context['reconciliation_outcome'] = $outcome;
        }

        $this->auditLogger->log($action, 'import_content_object', null, $context);
    }

    /**
     * @param array{sha256:string,byte_size:int,correlation_id:?string} $normalized
     */
    private function auditConflict(?ImportContentObject $content, array $normalized): void
    {
        $this->auditLogger->log('CONTENT_HASH_METADATA_CONFLICT', 'import_content_object', null, [
            'content_object_id' => $content === null ? null : (int) $content->getKey(),
            'correlation_id' => $normalized['correlation_id'],
            'conflict_code' => 'CONTENT_HASH_METADATA_CONFLICT',
            'reconciliation_outcome' => 'RECONCILIATION_REQUIRED',
        ]);
    }
}
