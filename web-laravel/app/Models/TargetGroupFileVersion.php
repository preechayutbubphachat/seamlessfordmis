<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

final class TargetGroupFileVersion extends Model
{
    protected $table = 'target_group_file_versions';

    protected $fillable = [
        'lineage_id',
        'version_token',
        'version_number',
        'target_group_file_id',
        'target_group_job_id',
        'previous_version_id',
        'superseded_by_id',
        'version_status',
        'correction_reason',
        'supersession_reason',
        'superseded_at',
        'superseded_by_user_id',
        'confirmed_by_user_id',
        'confirmed_at',
        'correlation_id',
    ];

    protected static function booted(): void
    {
        static::updating(function (self $version): void {
            foreach (['lineage_id', 'version_token', 'version_number'] as $field) {
                if ($version->isDirty($field)) {
                    throw new \LogicException("Immutable version identity field cannot be changed: {$field}");
                }
            }
        });
    }

    public function lineage(): BelongsTo
    {
        return $this->belongsTo(TargetGroupLineage::class, 'lineage_id', 'lineage_id');
    }

    public function file(): BelongsTo
    {
        return $this->belongsTo(TargetGroupFile::class, 'target_group_file_id');
    }

    public function job(): BelongsTo
    {
        return $this->belongsTo(TargetGroupJob::class, 'target_group_job_id');
    }

    public function previousVersion(): BelongsTo
    {
        return $this->belongsTo(self::class, 'previous_version_id');
    }

    public function supersededBy(): BelongsTo
    {
        return $this->belongsTo(self::class, 'superseded_by_id');
    }

    public function supersessionAsPredecessor(): HasMany
    {
        return $this->hasMany(TargetGroupVersionSupersession::class, 'predecessor_version_id');
    }

    public function supersessionAsSuccessor(): HasMany
    {
        return $this->hasMany(TargetGroupVersionSupersession::class, 'successor_version_id');
    }

    protected function casts(): array
    {
        return [
            'version_number' => 'integer',
            'superseded_at' => 'datetime',
            'confirmed_at' => 'datetime',
        ];
    }
}
