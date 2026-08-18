<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

final class SourceImportRow extends Model
{
    protected $fillable = [
        'source_import_job_id',
        'source_file_id',
        'sheet_name',
        'row_number',
        'raw_payload',
        'raw_cid',
        'normalized_cid',
        'cid_status',
        'raw_full_name',
        'normalized_full_name',
        'raw_service_text',
        'normalized_service_key',
        'raw_visit_date',
        'normalized_visit_date',
        'validation_status',
        'review_reason',
        'matching_key_version',
        'normalization_version',
        'validation_version',
        'scope_context_id',
    ];

    public function job(): BelongsTo
    {
        return $this->belongsTo(SourceImportJob::class, 'source_import_job_id');
    }

    public function file(): BelongsTo
    {
        return $this->belongsTo(SourceImportFile::class, 'source_file_id');
    }

    protected function casts(): array
    {
        return [
            'raw_payload' => 'array',
            'normalized_visit_date' => 'date',
        ];
    }
}
