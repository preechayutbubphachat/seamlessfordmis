<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

final class TargetGroupHistoryRow extends Model
{
    protected $fillable = [
        'target_group_job_id',
        'target_group_row_id',
        'target_group_file_id',
        'sheet_name',
        'row_number',
        'raw_payload',
        'raw_service_text',
        'normalized_service_key',
        'raw_visit_date',
        'normalized_visit_date',
        'evidence_source',
        'provenance',
    ];

    public function job(): BelongsTo
    {
        return $this->belongsTo(TargetGroupJob::class, 'target_group_job_id');
    }

    public function row(): BelongsTo
    {
        return $this->belongsTo(TargetGroupRow::class, 'target_group_row_id');
    }

    public function file(): BelongsTo
    {
        return $this->belongsTo(TargetGroupFile::class, 'target_group_file_id');
    }

    protected function casts(): array
    {
        return [
            'raw_payload' => 'array',
            'provenance' => 'array',
            'normalized_visit_date' => 'date',
        ];
    }
}
