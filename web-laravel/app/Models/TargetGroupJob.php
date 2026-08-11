<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

final class TargetGroupJob extends Model
{
    protected $fillable = [
        'created_by_user_id',
        'group_name',
        'status',
        'total_files',
        'total_rows',
        'valid_rows',
        'invalid_rows',
        'review_rows',
        'source_set_hash',
        'error_message',
        'started_at',
        'finished_at',
        'import_request_id',
        'retry_of_job_id',
    ];

    public function files(): HasMany
    {
        return $this->hasMany(TargetGroupFile::class);
    }

    public function rows(): HasMany
    {
        return $this->hasMany(TargetGroupRow::class);
    }

    public function historyRows(): HasMany
    {
        return $this->hasMany(TargetGroupHistoryRow::class);
    }

    public function importRequest(): BelongsTo
    {
        return $this->belongsTo(TargetGroupImportRequest::class, 'import_request_id', 'import_request_id');
    }

    public function retryOfJob(): BelongsTo
    {
        return $this->belongsTo(self::class, 'retry_of_job_id');
    }

    public function retryJobs(): HasMany
    {
        return $this->hasMany(self::class, 'retry_of_job_id');
    }

    public function attempts(): HasMany
    {
        return $this->hasMany(TargetGroupJobAttempt::class, 'job_id');
    }

    public function versions(): HasMany
    {
        return $this->hasMany(TargetGroupFileVersion::class, 'target_group_job_id');
    }

    protected function casts(): array
    {
        return [
            'started_at' => 'datetime',
            'finished_at' => 'datetime',
        ];
    }
}
