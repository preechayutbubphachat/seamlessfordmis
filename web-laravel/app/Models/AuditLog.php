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
    ];

    public function actor(): BelongsTo
    {
        return $this->belongsTo(User::class, 'actor_user_id');
    }

    protected function casts(): array
    {
        return [
            'before_payload' => 'array',
            'after_payload' => 'array',
            'conflict_flags' => 'array',
            'created_at' => 'datetime',
            'reviewed_at' => 'datetime',
        ];
    }
}
