<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use LogicException;

final class TargetGroupRowReview extends Model
{
    public $timestamps = false;

    protected $fillable = [
        'target_group_job_id',
        'target_group_file_id',
        'target_group_row_id',
        'reviewed_by',
        'correlation_id',
        'from_status',
        'to_status',
        'review_outcome',
        'review_reason_code',
        'matching_key_type',
        'matching_key_version',
        'normalization_version',
        'validation_version',
        'conflict_flags',
        'evidence_references',
        'operator_note',
        'reviewed_at',
        'created_at',
    ];

    public function row(): BelongsTo
    {
        return $this->belongsTo(TargetGroupRow::class, 'target_group_row_id');
    }

    public function reviewer(): BelongsTo
    {
        return $this->belongsTo(User::class, 'reviewed_by');
    }

    protected function casts(): array
    {
        return [
            'conflict_flags' => 'array',
            'evidence_references' => 'array',
            'reviewed_at' => 'datetime',
            'created_at' => 'datetime',
        ];
    }

    protected function performUpdate(Builder $query): bool
    {
        throw new LogicException('D6 review events are append-only.');
    }

    protected function performDeleteOnModel(): void
    {
        throw new LogicException('D6 review events are append-only.');
    }
}
