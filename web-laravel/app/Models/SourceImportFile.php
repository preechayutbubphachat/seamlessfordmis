<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

final class SourceImportFile extends Model
{
    protected $fillable = [
        'source_import_job_id',
        'original_filename',
        'stored_path',
        'mime_type',
        'size_bytes',
        'sha256',
        'sheet_count',
        'row_count',
    ];

    public function job(): BelongsTo
    {
        return $this->belongsTo(SourceImportJob::class, 'source_import_job_id');
    }

    public function rows(): HasMany
    {
        return $this->hasMany(SourceImportRow::class, 'source_file_id');
    }
}
