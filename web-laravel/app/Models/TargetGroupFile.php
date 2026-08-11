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
        'content_object_id',
    ];

    public function job(): BelongsTo
    {
        return $this->belongsTo(TargetGroupJob::class, 'target_group_job_id');
    }

    public function contentObject(): BelongsTo
    {
        return $this->belongsTo(ImportContentObject::class, 'content_object_id');
    }

    public function rows(): HasMany
    {
        return $this->hasMany(TargetGroupRow::class);
    }

    public function historyRows(): HasMany
    {
        return $this->hasMany(TargetGroupHistoryRow::class);
    }

    public function versions(): HasMany
    {
        return $this->hasMany(TargetGroupFileVersion::class, 'target_group_file_id');
    }
}
