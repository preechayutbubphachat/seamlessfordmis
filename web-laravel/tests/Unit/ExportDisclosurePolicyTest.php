<?php

namespace Tests\Unit;

use App\Services\Export\ExportDisclosurePolicy;
use DomainException;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

final class ExportDisclosurePolicyTest extends TestCase
{
    public function test_policy_version_and_allowed_column_order_are_deterministic(): void
    {
        $policy = new ExportDisclosurePolicy();

        $this->assertSame('deidentified_internal_v1', $policy->version());
        $this->assertSame([
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
        ], $policy->allowedColumns());
        $this->assertSame($policy->allowedColumns(), $policy->validateColumnSelection(
            array_reverse($policy->allowedColumns())
        ));
    }

    public function test_every_authorized_column_is_accepted(): void
    {
        $policy = new ExportDisclosurePolicy();

        foreach ($policy->allowedColumns() as $column) {
            $this->assertSame([$column], $policy->validateColumnSelection([$column]));
        }
    }

    #[DataProvider('rejectedColumnProvider')]
    public function test_prohibited_unknown_and_case_varied_columns_are_rejected(string $column): void
    {
        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('Export column selection contains a prohibited or unknown field.');

        (new ExportDisclosurePolicy())->validateColumnSelection([$column]);
    }

    public static function rejectedColumnProvider(): array
    {
        return [
            'raw CID' => ['raw_cid'],
            'normalized CID' => ['normalized_cid'],
            'display name' => ['display_name'],
            'birth date' => ['birth_date'],
            'raw payload' => ['raw_payload'],
            'review reason' => ['review_reason'],
            'complete provenance' => ['provenance'],
            'unknown' => ['synthetic_unknown_column'],
            'case variation' => ['RAW_CID'],
        ];
    }

    public function test_mixed_selection_fails_without_silently_dropping_forbidden_field(): void
    {
        $policy = new ExportDisclosurePolicy();

        try {
            $policy->validateColumnSelection(['result_category', 'display_name']);
            $this->fail('Mixed allowed and prohibited selections must fail completely.');
        } catch (DomainException $exception) {
            $this->assertSame(
                'Export column selection contains a prohibited or unknown field.',
                $exception->getMessage(),
            );
        }
    }
}
