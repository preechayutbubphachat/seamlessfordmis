<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Model;

final class SourceImportJob extends Model
{
    protected $fillable = [
        'created_by_user_id',
        'job_name',
        'status',
        'total_files',
        'total_rows',
        'valid_rows',
        'invalid_rows',
        'review_rows',
        'error_message',
        'started_at',
        'finished_at',
    ];

    public function files(): HasMany
    {
        return $this->hasMany(SourceImportFile::class);
    }

    public function rows(): HasMany
    {
        return $this->hasMany(SourceImportRow::class);
    }

    protected function casts(): array
    {
        return [
            'started_at' => 'datetime',
            'finished_at' => 'datetime',
        ];
    }
}
