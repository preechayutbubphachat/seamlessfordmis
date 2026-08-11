<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

final class TargetGroupJobAttempt extends Model
{
    protected $table = 'target_group_job_attempts';
    protected $primaryKey = 'attempt_id';
    public $incrementing = false;
    protected $keyType = 'string';
    public $timestamps = false;

    protected $fillable = [
        'attempt_id',
        'job_id',
        'attempt_number',
        'state',
        'worker_token',
        'lease_acquired_at',
        'lease_expires_at',
        'started_at',
        'finished_at',
        'last_heartbeat_at',
        'failure_code',
        'last_error_code',
        'retryable',
        'reconciliation_state',
        'reconciliation_reference',
        'correlation_id',
        'created_at',
    ];

    public function job(): BelongsTo
    {
        return $this->belongsTo(TargetGroupJob::class, 'job_id');
    }

    protected function casts(): array
    {
        return [
            'retryable' => 'boolean',
            'lease_acquired_at' => 'datetime',
            'lease_expires_at' => 'datetime',
            'started_at' => 'datetime',
            'finished_at' => 'datetime',
            'last_heartbeat_at' => 'datetime',
            'created_at' => 'datetime',
        ];
    }
}
