<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

final class TargetGroupImportRequest extends Model
{
    protected $table = 'import_requests';
    protected $primaryKey = 'import_request_id';
    public $incrementing = false;
    protected $keyType = 'string';

    protected $fillable = [
        'import_request_id',
        'operation',
        'lifecycle_state',
        'context_fingerprint',
        'canonical_job_id',
        'correlation_id',
        'created_by_user_id',
        'created_at',
        'completed_at',
        'failure_code',
        'reconciliation_state',
        'reconciliation_reference',
    ];

    public function canonicalJob(): BelongsTo
    {
        return $this->belongsTo(TargetGroupJob::class, 'canonical_job_id');
    }

    public function jobs(): HasMany
    {
        return $this->hasMany(TargetGroupJob::class, 'import_request_id', 'import_request_id');
    }

    protected function casts(): array
    {
        return [
            'created_at' => 'datetime',
            'completed_at' => 'datetime',
        ];
    }
}
