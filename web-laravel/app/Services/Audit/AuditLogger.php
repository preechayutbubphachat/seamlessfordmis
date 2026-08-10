<?php

namespace App\Services\Audit;

use Illuminate\Support\Facades\DB;

final class AuditLogger
{
    public function log(string $action, string $entityType, ?int $entityId = null, array $context = []): void
    {
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
        ]);
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
