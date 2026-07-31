<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

final class TargetGroupRow extends Model
{
    protected $fillable = [
        'target_group_job_id',
        'target_group_file_id',
        'sheet_name',
        'row_number',
        'raw_payload',
        'raw_cid',
        'normalized_cid',
        'cid_status',
        'raw_full_name',
        'normalized_full_name',
        'raw_birth_date',
        'normalized_birth_date',
        'validation_status',
        'review_reason',
    ];

    public function job(): BelongsTo
    {
        return $this->belongsTo(TargetGroupJob::class, 'target_group_job_id');
    }

    public function file(): BelongsTo
    {
        return $this->belongsTo(TargetGroupFile::class, 'target_group_file_id');
    }

    public function historyRows(): HasMany
    {
        return $this->hasMany(TargetGroupHistoryRow::class);
    }

    protected function casts(): array
    {
        return [
            'raw_payload' => 'array',
            'normalized_birth_date' => 'date',
        ];
    }
}
