<?php

namespace App\Services\Export;

use DomainException;

final class ExportDisclosurePolicy
{
    public const VERSION = 'deidentified_internal_v1';

    public const ALLOWED_COLUMNS = [
        'export_sequence',
        'result_category',
        'review_status',
        'latest_history_date',
        'latest_history_source',
        'evidence_source_count',
        'provenance_available',
        'selected_service_keys',
        'target_group_job_id',
        'result_generation_job_id',
    ];

    public const PROHIBITED_FIELDS = [
        'raw_cid',
        'normalized_cid',
        'cid',
        'display_identifier',
        'raw_name',
        'normalized_name',
        'display_name',
        'first_name',
        'last_name',
        'birth_date',
        'raw_payload',
        'provenance',
        'uploaded_source_row_contents',
        'address',
        'addresses',
        'phone',
        'phone_number',
        'credentials',
        'absolute_storage_path',
        'review_reason',
    ];

    public function version(): string
    {
        return self::VERSION;
    }

    public function allowedColumns(): array
    {
        return self::ALLOWED_COLUMNS;
    }

    public function prohibitedFields(): array
    {
        return self::PROHIBITED_FIELDS;
    }

    public function validateColumnSelection(array $columns): array
    {
        $normalized = array_map(
            static fn (mixed $column): string => strtolower(trim((string) $column)),
            $columns,
        );

        if (count($normalized) !== count(array_unique($normalized))) {
            throw new DomainException('Export column selection contains duplicate fields.');
        }

        foreach ($normalized as $column) {
            if (! in_array($column, self::ALLOWED_COLUMNS, true)) {
                throw new DomainException('Export column selection contains a prohibited or unknown field.');
            }
        }

        return array_values(array_filter(
            self::ALLOWED_COLUMNS,
            static fn (string $column): bool => in_array($column, $normalized, true),
        ));
    }
}
