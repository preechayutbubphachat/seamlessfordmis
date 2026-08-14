<?php

namespace App\Services\Audit;

use Illuminate\Support\Facades\DB;
use LogicException;

final class AuditLogger
{
    private const D8_TYPED_FIELDS = [
        'import_request_id',
        'content_object_id',
        'conflict_code',
        'reconciliation_outcome',
    ];

    public function log(string $action, string $entityType, ?int $entityId = null, array $context = []): void
    {
        $typed = $this->typedD8Context($context);

        DB::table('audit_logs')->insert([
            'actor_user_id' => $context['actor_user_id'] ?? null,
            'action' => $action,
            'entity_type' => $entityType,
            'entity_id' => $entityId,
            'ip_address' => $context['ip_address'] ?? null,
            'user_agent' => $context['user_agent'] ?? null,
            'before_payload' => isset($context['before_payload']) ? json_encode($this->privacySafePayload($context['before_payload']), JSON_THROW_ON_ERROR) : null,
            'after_payload' => isset($context['after_payload']) ? json_encode($this->privacySafePayload($context['after_payload']), JSON_THROW_ON_ERROR) : null,
            'correlation_id' => $context['correlation_id'] ?? null,
            'target_group_job_id' => $context['target_group_job_id'] ?? null,
            'target_group_file_id' => $context['target_group_file_id'] ?? null,
            'target_group_row_id' => $context['target_group_row_id'] ?? null,
            'matching_key_type' => $context['matching_key_type'] ?? null,
            'matching_key_version' => $context['matching_key_version'] ?? null,
            'review_reason_code' => $context['review_reason_code'] ?? null,
            'review_outcome' => $context['review_outcome'] ?? null,
            'conflict_flags' => isset($context['conflict_flags']) ? json_encode($this->privacySafePayload($context['conflict_flags']), JSON_THROW_ON_ERROR) : null,
            'reviewed_by' => $context['reviewed_by'] ?? null,
            'reviewed_at' => $context['reviewed_at'] ?? null,
            'created_at' => now(),
            'import_request_id' => $typed['import_request_id'],
            'content_object_id' => $typed['content_object_id'],
            'conflict_code' => $typed['conflict_code'],
            'reconciliation_outcome' => $typed['reconciliation_outcome'],
        ]);
    }

    /**
     * @return array{import_request_id:?string,content_object_id:?int,conflict_code:?string,reconciliation_outcome:?string}
     */
    private function typedD8Context(array $context): array
    {
        $typed = array_fill_keys(self::D8_TYPED_FIELDS, null);

        if (array_key_exists('import_request_id', $context) && $context['import_request_id'] !== null) {
            if (! is_string($context['import_request_id']) || preg_match('/\A[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\z/', $context['import_request_id']) !== 1) {
                throw new LogicException('D8_AUDIT_IMPORT_REQUEST_ID_INVALID');
            }
            $typed['import_request_id'] = $context['import_request_id'];
        }

        if (array_key_exists('content_object_id', $context) && $context['content_object_id'] !== null) {
            if (! is_int($context['content_object_id']) || $context['content_object_id'] < 1) {
                throw new LogicException('D8_AUDIT_CONTENT_OBJECT_ID_INVALID');
            }
            $typed['content_object_id'] = $context['content_object_id'];
        }

        foreach (['conflict_code', 'reconciliation_outcome'] as $field) {
            if (! array_key_exists($field, $context) || $context[$field] === null) {
                continue;
            }

            if (! is_string($context[$field]) || preg_match('/\A[A-Z0-9_]{1,64}\z/', $context[$field]) !== 1) {
                throw new LogicException("D8_AUDIT_{$field}_INVALID");
            }
            $typed[$field] = $context[$field];
        }

        return $typed;
    }

    private function privacySafePayload(mixed $payload): mixed
    {
        if (! is_array($payload)) {
            return $payload;
        }

        $sensitiveKeys = [
            'cid',
            'raw_cid',
            'normalized_cid',
            'raw_payload',
            'patient',
            'name',
            'raw_full_name',
            'normalized_full_name',
            'birth_date',
            'raw_birth_date',
            'normalized_birth_date',
        ];
        $safe = [];

        foreach ($payload as $key => $value) {
            $safe[$key] = in_array(strtolower((string) $key), $sensitiveKeys, true)
                ? '[REDACTED]'
                : $this->privacySafePayload($value);
        }

        return $safe;
    }
}
