<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

final class TargetGroupVersionSupersession extends Model
{
    protected $table = 'target_group_version_supersessions';

    protected $fillable = [
        'predecessor_version_id',
        'successor_version_id',
        'committed_by_user_id',
        'correlation_id',
        'supersession_reason',
        'committed_at',
    ];

    public function predecessor(): BelongsTo
    {
        return $this->belongsTo(TargetGroupFileVersion::class, 'predecessor_version_id');
    }

    public function successor(): BelongsTo
    {
        return $this->belongsTo(TargetGroupFileVersion::class, 'successor_version_id');
    }

    protected function casts(): array
    {
        return [
            'committed_at' => 'datetime',
        ];
    }
}
