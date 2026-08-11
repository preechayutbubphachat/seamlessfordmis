<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

final class AuditLog extends Model
{
    public $timestamps = false;

    protected $fillable = [
        'actor_user_id',
        'action',
        'entity_type',
        'entity_id',
        'ip_address',
        'user_agent',
        'before_payload',
        'after_payload',
        'created_at',
        'correlation_id',
        'target_group_job_id',
        'target_group_file_id',
        'target_group_row_id',
        'matching_key_type',
        'matching_key_version',
        'review_reason_code',
        'review_outcome',
        'conflict_flags',
        'reviewed_by',
        'reviewed_at',
        'import_request_id',
        'content_object_id',
        'attempt_id',
        'lineage_id',
        'version_id',
        'version_token',
        'version_number',
        'predecessor_version_id',
        'successor_version_id',
        'conflict_code',
        'reconciliation_outcome',
    ];

    public function actor(): BelongsTo
    {
        return $this->belongsTo(User::class, 'actor_user_id');
    }

    public function importRequest(): BelongsTo
    {
        return $this->belongsTo(TargetGroupImportRequest::class, 'import_request_id', 'import_request_id');
    }

    public function contentObject(): BelongsTo
    {
        return $this->belongsTo(ImportContentObject::class, 'content_object_id');
    }

    public function attempt(): BelongsTo
    {
        return $this->belongsTo(TargetGroupJobAttempt::class, 'attempt_id', 'attempt_id');
    }

    public function lineage(): BelongsTo
    {
        return $this->belongsTo(TargetGroupLineage::class, 'lineage_id', 'lineage_id');
    }

    public function version(): BelongsTo
    {
        return $this->belongsTo(TargetGroupFileVersion::class, 'version_id');
    }

    public function predecessorVersion(): BelongsTo
    {
        return $this->belongsTo(TargetGroupFileVersion::class, 'predecessor_version_id');
    }

    public function successorVersion(): BelongsTo
    {
        return $this->belongsTo(TargetGroupFileVersion::class, 'successor_version_id');
    }

    protected function casts(): array
    {
        return [
            'before_payload' => 'array',
            'after_payload' => 'array',
            'conflict_flags' => 'array',
            'created_at' => 'datetime',
            'reviewed_at' => 'datetime',
            'version_number' => 'integer',
        ];
    }
}
