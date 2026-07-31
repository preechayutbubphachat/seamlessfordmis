<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

final class TargetGroupFile extends Model
{
    protected $fillable = [
        'target_group_job_id',
        'original_filename',
        'stored_path',
        'mime_type',
        'size_bytes',
        'sha256',
        'sheet_count',
        'row_count',
    ];

    public function job(): BelongsTo
    {
        return $this->belongsTo(TargetGroupJob::class, 'target_group_job_id');
    }

    public function rows(): HasMany
    {
        return $this->hasMany(TargetGroupRow::class);
    }

    public function historyRows(): HasMany
    {
        return $this->hasMany(TargetGroupHistoryRow::class);
    }
}
