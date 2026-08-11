<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

final class TargetGroupLineage extends Model
{
    protected $table = 'target_group_lineages';
    protected $primaryKey = 'lineage_id';
    public $incrementing = false;
    protected $keyType = 'string';

    protected $fillable = [
        'lineage_id',
        'next_version_number',
        'active_version_id',
    ];

    public function versions(): HasMany
    {
        return $this->hasMany(TargetGroupFileVersion::class, 'lineage_id', 'lineage_id');
    }

    public function activeVersion(): BelongsTo
    {
        return $this->belongsTo(TargetGroupFileVersion::class, 'active_version_id');
    }
}
