<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
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

    protected function casts(): array
    {
        return [
            'started_at' => 'datetime',
            'finished_at' => 'datetime',
        ];
    }
}
