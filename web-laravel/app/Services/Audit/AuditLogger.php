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
            'before_payload' => isset($context['before_payload']) ? json_encode($context['before_payload']) : null,
            'after_payload' => isset($context['after_payload']) ? json_encode($context['after_payload']) : null,
            'created_at' => now(),
        ]);
    }
}
