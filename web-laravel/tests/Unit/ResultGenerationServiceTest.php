<?php

namespace Tests\Unit;

use App\Services\Result\ResultGenerationService;
use PHPUnit\Framework\TestCase;

final class ResultGenerationServiceTest extends TestCase
{
    private ResultGenerationService $service;

    protected function setUp(): void
    {
        parent::setUp();

        $this->service = new ResultGenerationService();
    }

    public function test_valid_cid_with_source_db_history_has_history(): void
    {
        $draft = $this->service->buildPersonResultDraft(
            ['raw_cid' => '1234567890121', 'raw_payload' => ['synthetic_row' => 'target']],
            [$this->history('screening_db', 'alpha', '2026-01-10', 'db-ref-1')],
            ['alpha']
        );

        $this->assertSame(ResultGenerationService::CATEGORY_HAS_HISTORY, $draft['result_category']);
        $this->assertTrue($draft['has_screening_db_history']);
        $this->assertFalse($draft['has_target_group_file_history']);
        $this->assertSame('2026-01-10', $draft['latest_history_date']);
    }

    public function test_valid_cid_with_target_group_file_history_is_not_no_history(): void
    {
        $draft = $this->service->buildPersonResultDraft(
            ['raw_cid' => '1234567890121', 'raw_payload' => ['synthetic_row' => 'target']],
            [$this->history('target_group_file', 'alpha', '2026-02-03', 'file-ref-1')],
            ['alpha']
        );

        $this->assertSame(ResultGenerationService::CATEGORY_HAS_HISTORY, $draft['result_category']);
        $this->assertFalse($draft['has_screening_db_history']);
        $this->assertTrue($draft['has_target_group_file_history']);
        $this->assertTrue($draft['has_any_history']);
    }

    public function test_valid_cid_with_no_history_is_no_history(): void
    {
        $draft = $this->service->buildPersonResultDraft(
            ['raw_cid' => '1234567890121', 'raw_payload' => ['synthetic_row' => 'target']],
            [],
            ['alpha']
        );

        $this->assertSame(ResultGenerationService::CATEGORY_NO_HISTORY, $draft['result_category']);
        $this->assertFalse($draft['has_any_history']);
        $this->assertNull($draft['latest_history_date']);
    }

    public function test_invalid_cid_is_invalid_identifier_not_no_history(): void
    {
        $draft = $this->service->buildPersonResultDraft(
            ['raw_cid' => '1234567890129', 'raw_payload' => ['synthetic_row' => 'target']],
            [],
            ['alpha']
        );

        $this->assertSame(ResultGenerationService::CATEGORY_INVALID_IDENTIFIER, $draft['result_category']);
        $this->assertSame('invalid_identifier', $draft['identifier_status']);
        $this->assertFalse($draft['has_any_history']);
    }

    public function test_missing_cid_is_missing_identifier_not_no_history(): void
    {
        $draft = $this->service->buildPersonResultDraft(
            ['raw_cid' => '', 'raw_payload' => ['synthetic_row' => 'target']],
            [],
            ['alpha']
        );

        $this->assertSame(ResultGenerationService::CATEGORY_MISSING_IDENTIFIER, $draft['result_category']);
        $this->assertSame('missing_identifier', $draft['identifier_status']);
        $this->assertFalse($draft['has_any_history']);
    }

    public function test_latest_history_date_uses_selected_service_keys_only(): void
    {
        $latest = $this->service->selectLatestHistoryForServices([
            $this->history('screening_db', 'alpha', '2026-01-10', 'db-ref-1'),
            $this->history('screening_db', 'beta', '2026-12-31', 'db-ref-2'),
            $this->history('target_group_file', 'alpha', '2026-03-15', 'file-ref-1'),
        ], ['alpha']);

        $this->assertSame('2026-03-15', $latest['evidence_date']);
        $this->assertSame('alpha', $latest['normalized_service_key']);
        $this->assertSame('target_group_file', $latest['source_type']);
    }

    public function test_unrelated_service_history_does_not_affect_latest_history_date(): void
    {
        $draft = $this->service->buildPersonResultDraft(
            ['raw_cid' => '1234567890121', 'raw_payload' => ['synthetic_row' => 'target']],
            [$this->history('screening_db', 'beta', '2026-12-31', 'db-ref-2')],
            ['alpha']
        );

        $this->assertSame(ResultGenerationService::CATEGORY_NO_HISTORY, $draft['result_category']);
        $this->assertFalse($draft['has_any_history']);
        $this->assertNull($draft['latest_history_date']);
    }

    public function test_evidence_summary_includes_source_type_and_provenance_reference(): void
    {
        $summary = $this->service->summarizeHistoryEvidence([
            $this->history('target_group_file', 'alpha', '2026-02-03', 'file-ref-1'),
        ], ['alpha']);

        $this->assertSame('target_group_file', $summary['sources'][0]['source_type']);
        $this->assertSame(['reference' => 'file-ref-1'], $summary['sources'][0]['provenance']);
    }

    public function test_one_person_result_builds_one_draft_row(): void
    {
        $draft = $this->service->buildPersonResultDraft(
            ['raw_cid' => '1234567890121', 'raw_payload' => ['synthetic_row' => 'target']],
            [$this->history('screening_db', 'alpha', '2026-01-10', 'db-ref-1')],
            ['alpha']
        );

        $this->assertSame('1234567890121', $draft['person_key']);
        $this->assertSame('1234567890121', $draft['normalized_cid']);
        $this->assertArrayHasKey('evidence_summary', $draft);
    }

    public function test_ambiguous_identity_requires_review(): void
    {
        $draft = $this->service->buildPersonResultDraft(
            [
                'raw_cid' => '1234567890121',
                'identity_ambiguous' => true,
                'raw_payload' => ['synthetic_row' => 'target'],
            ],
            [$this->history('screening_db', 'alpha', '2026-01-10', 'db-ref-1')],
            ['alpha']
        );

        $this->assertSame(ResultGenerationService::CATEGORY_NEEDS_REVIEW, $draft['result_category']);
    }

    public function test_raw_source_payload_is_preserved_in_draft(): void
    {
        $draft = $this->service->buildPersonResultDraft(
            ['raw_cid' => '1234567890121', 'raw_payload' => ['synthetic_raw_value' => 'kept']],
            [],
            ['alpha']
        );

        $this->assertSame(['synthetic_raw_value' => 'kept'], $draft['raw_payload']);
    }

    private function history(string $sourceType, string $serviceKey, string $date, string $reference): array
    {
        return [
            'source_type' => $sourceType,
            'normalized_service_key' => $serviceKey,
            'evidence_date' => $date,
            'provenance' => ['reference' => $reference],
            'source_payload' => ['synthetic_history' => $reference],
        ];
    }
}
