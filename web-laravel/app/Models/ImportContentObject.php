<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

final class ImportContentObject extends Model
{
    public $timestamps = false;

    protected $fillable = [
        'sha256',
        'byte_size',
        'registered_at',
    ];

    public function targetGroupFiles(): HasMany
    {
        return $this->hasMany(TargetGroupFile::class, 'content_object_id');
    }

    protected function casts(): array
    {
        return [
            'byte_size' => 'integer',
            'registered_at' => 'datetime',
        ];
    }
}
