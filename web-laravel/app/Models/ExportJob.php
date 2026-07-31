<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

final class ExportJob extends Model
{
    protected $fillable = [
        'export_type',
        'status',
        'requested_by_user_id',
        'filters',
        'stored_path',
        'row_count',
        'error_message',
        'started_at',
        'finished_at',
        'generated_filename',
        'mime_type',
        'byte_count',
        'sha256',
    ];

    protected function casts(): array
    {
        return [
            'filters' => 'array',
            'row_count' => 'integer',
            'byte_count' => 'integer',
            'started_at' => 'datetime',
            'finished_at' => 'datetime',
        ];
    }
}
