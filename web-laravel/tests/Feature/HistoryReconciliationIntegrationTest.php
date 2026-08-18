<?php

namespace Tests\Feature;

use App\Services\CidValidator;
use App\Services\History\HistoryReconciliationService;
use App\Services\Result\ResultGenerationService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

final class HistoryReconciliationIntegrationTest extends TestCase
{
    use RefreshDatabase;

    private const CID = '1234567890121';
    private const SCOPE = 'SCOPE-0:synthetic-lineage';
    private const LINEAGE = '11111111-1111-4111-8111-111111111111';
    private const VERSION_ID = 101;

    public function test_valid_cid_with_one_compatible_history_is_found(): void
    {
        $decision = $this->service()->reconcile(
            $this->subject(),
            [$this->history()],
            ['alpha'],
        );

        $this->assertSame(ResultGenerationService::CATEGORY_HAS_HISTORY, $decision['result_category']);
        $this->assertSame('not_required', $decision['review_status']);
        $this->assertSame('cid:'.self::CID, $decision['person_key']);
        $this->assertCount(1, $decision['evidence_summary']['sources']);
    }

    public function test_multiple_legitimate_history_rows_are_found_and_preserved(): void
    {
        $decision = $this->service()->reconcile(
            $this->subject(),
            [
                $this->history(['visit_date' => '2026-01-10']),
                $this->history(['visit_date' => '2026-02-10', 'source_row_id' => 22]),
            ],
            ['alpha'],
        );

        $this->assertSame(ResultGenerationService::CATEGORY_HAS_HISTORY, $decision['result_category']);
        $this->assertCount(2, $decision['evidence_summary']['sources']);
        $this->assertSame(22, $decision['evidence_summary']['sources'][1]['provenance']['row_id']);
    }

    public function test_valid_cid_with_no_compatible_history_is_no_history(): void
    {
        $decision = $this->service()->reconcile($this->subject(), [], ['alpha']);

        $this->assertSame(ResultGenerationService::CATEGORY_NO_HISTORY, $decision['result_category']);
        $this->assertFalse($decision['has_any_history']);
    }

    #[DataProvider('invalidIdentityProvider')]
    public function test_invalid_identity_never_becomes_no_history(?string $cid, string $reason): void
    {
        $subject = $this->subject(['raw_cid' => $cid, 'normalized_cid' => null]);
        $decision = $this->service()->reconcile($subject, [], ['alpha']);

        $this->assertSame(ResultGenerationService::CATEGORY_NEEDS_REVIEW, $decision['result_category']);
        $this->assertSame('needs_review', $decision['review_status']);
        $this->assertSame($reason, $decision['review_reason']);
        $this->assertSame('unresolved', $decision['person_key']);
        $this->assertNull($decision['normalized_cid']);
    }

    public static function invalidIdentityProvider(): array
    {
        return [
            'missing' => [null, 'MISSING_CID'],
            'invalid format' => ['not-a-cid', 'INVALID_CID_FORMAT'],
            'invalid check digit' => ['1234567890129', 'INVALID_CID_CHECK_DIGIT'],
        ];
    }

    public function test_authoritative_identity_metadata_mismatch_fails_closed(): void
    {
        $decision = $this->service()->reconcile(
            $this->subject(['matching_key_version' => 'cid-v0']),
            [$this->history()],
            ['alpha'],
        );

        $this->assertSame(ResultGenerationService::CATEGORY_NEEDS_REVIEW, $decision['result_category']);
        $this->assertSame('AMBIGUOUS_HISTORY', $decision['review_reason']);
    }

    public function test_name_and_birth_date_conflicts_use_existing_review_reasons(): void
    {
        $nameConflict = $this->service()->reconcile(
            $this->subject(),
            [$this->history(['full_name' => 'SYN OTHER'])],
            ['alpha'],
        );
        $birthConflict = $this->service()->reconcile(
            $this->subject(),
            [$this->history(['birth_date' => '1991-01-01'])],
            ['alpha'],
        );

        $this->assertSame('NAME_CONFLICT', $nameConflict['review_reason']);
        $this->assertSame('BIRTH_DATE_CONFLICT', $birthConflict['review_reason']);
    }

    public function test_ambiguity_and_source_conflict_fail_closed(): void
    {
        $ambiguous = $this->service()->reconcile(
            $this->subject(),
            [$this->history(['identity_ambiguous' => true])],
            ['alpha'],
        );
        $conflict = $this->service()->reconcile(
            $this->subject(),
            [$this->history(['source_conflict' => true])],
            ['alpha'],
        );

        $this->assertSame('AMBIGUOUS_HISTORY', $ambiguous['review_reason']);
        $this->assertSame('SOURCE_EVIDENCE_CONFLICT', $conflict['review_reason']);
    }

    public function test_scope_mismatch_or_unknown_scope_never_matches_globally(): void
    {
        $mismatch = $this->service()->reconcile(
            $this->subject(),
            [$this->history(['scope_context_id' => 'SCOPE-0:other-lineage'])],
            ['alpha'],
        );
        $unknown = $this->service()->reconcile(
            $this->subject(),
            [$this->history(['scope_context_id' => null])],
            ['alpha'],
        );

        $this->assertSame(ResultGenerationService::CATEGORY_NO_HISTORY, $mismatch['result_category']);
        $this->assertSame(ResultGenerationService::CATEGORY_NEEDS_REVIEW, $unknown['result_category']);
        $this->assertSame('AMBIGUOUS_HISTORY', $unknown['review_reason']);
    }

    public function test_selected_service_scope_is_isolated(): void
    {
        $decision = $this->service()->reconcile(
            $this->subject(),
            [$this->history(['normalized_service_key' => 'beta'])],
            ['alpha'],
        );

        $this->assertSame(ResultGenerationService::CATEGORY_NO_HISTORY, $decision['result_category']);
        $this->assertSame([], $decision['evidence_summary']['sources']);
    }

    public function test_relevant_legacy_evidence_without_metadata_prevents_false_no_history(): void
    {
        $legacy = $this->history([
            'matching_key_version' => null,
            'normalization_version' => null,
            'validation_version' => null,
            'producing_version_id' => null,
        ]);
        $decision = $this->service()->reconcile($this->subject(), [$legacy], ['alpha']);

        $this->assertSame(ResultGenerationService::CATEGORY_NEEDS_REVIEW, $decision['result_category']);
        $this->assertSame('AMBIGUOUS_HISTORY', $decision['review_reason']);
    }

    public function test_current_subject_must_be_the_active_d7_version(): void
    {
        $decision = $this->service()->reconcile(
            $this->subject(['active_version_id' => 102]),
            [$this->history()],
            ['alpha'],
        );

        $this->assertSame(ResultGenerationService::CATEGORY_NEEDS_REVIEW, $decision['result_category']);
        $this->assertSame('AMBIGUOUS_HISTORY', $decision['review_reason']);
    }

    public function test_corrected_successor_reconciles_against_preserved_prior_evidence(): void
    {
        $decision = $this->service()->reconcile(
            $this->subject([
                'active_version_id' => 102,
                'subject_version_id' => 102,
            ]),
            [$this->history(['producing_version_id' => 101])],
            ['alpha'],
        );

        $this->assertSame(ResultGenerationService::CATEGORY_HAS_HISTORY, $decision['result_category']);
        $this->assertCount(1, $decision['evidence_summary']['sources']);
        $this->assertSame(11, $decision['evidence_summary']['sources'][0]['provenance']['row_id']);
    }

    public function test_sensitive_identity_fields_are_removed_from_evidence_payload(): void
    {
        $decision = $this->service()->reconcile(
            $this->subject(),
            [$this->history([
                'source_payload' => [
                    'cid' => self::CID,
                    'full_name' => 'SYN ALPHA',
                    'birth_date' => '1990-01-01',
                    'safe_marker' => 'SYNTHETIC_SAFE',
                ],
            ])],
            ['alpha'],
        );

        $payload = $decision['evidence_summary']['sources'][0]['source_payload'];
        $this->assertArrayNotHasKey('cid', $payload);
        $this->assertArrayNotHasKey('full_name', $payload);
        $this->assertArrayNotHasKey('birth_date', $payload);
        $this->assertSame('SYNTHETIC_SAFE', $payload['safe_marker']);
    }

    public function test_same_result_replay_does_not_duplicate_projection_or_provenance(): void
    {
        $jobId = DB::table('target_group_jobs')->insertGetId([
            'group_name' => 'SYNTHETIC REPLAY',
            'status' => 'active',
            'total_files' => 0,
            'total_rows' => 0,
            'valid_rows' => 0,
            'invalid_rows' => 0,
            'review_rows' => 0,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        $draft = $this->service()->reconcile($this->subject(), [$this->history()], ['alpha']);

        $resultService = new ResultGenerationService();
        $resultService->persistResultDraftsForJob($jobId, [$draft], ['selected_service_keys' => ['alpha']]);
        $resultService->persistResultDraftsForJob($jobId, [$draft], ['selected_service_keys' => ['alpha']]);

        $this->assertSame(1, DB::table('result_generation_jobs')->count());
        $this->assertSame(1, DB::table('target_group_results')->count());
        $this->assertSame(1, DB::table('target_group_result_sources')->count());
    }

    public function test_migration_additive_columns_and_round_trip_are_safe(): void
    {
        $this->assertTrue(Schema::hasColumn('source_import_rows', 'matching_key_version'));
        $this->assertTrue(Schema::hasColumn('source_import_rows', 'normalization_version'));
        $this->assertTrue(Schema::hasColumn('source_import_rows', 'validation_version'));
        $this->assertTrue(Schema::hasColumn('target_group_rows', 'matching_key_version'));
        $this->assertTrue(Schema::hasColumn('target_group_rows', 'normalization_version'));
        $this->assertTrue(Schema::hasColumn('target_group_rows', 'validation_version'));
        $this->assertTrue(Schema::hasColumn('target_group_history_rows', 'normalized_cid'));
        $this->assertTrue(Schema::hasColumn('target_group_history_rows', 'target_group_file_version_id'));

        $migration = require base_path('database/migrations/2026_08_18_000020_add_history_reconciliation_identity_fields.php');
        $migration->down();
        $this->assertFalse(Schema::hasColumn('source_import_rows', 'matching_key_version'));
        $this->assertFalse(Schema::hasColumn('target_group_history_rows', 'normalized_cid'));

        $migration->up();
        $this->assertTrue(Schema::hasColumn('source_import_rows', 'matching_key_version'));
        $this->assertTrue(Schema::hasColumn('target_group_rows', 'matching_key_version'));
        $this->assertTrue(Schema::hasColumn('target_group_history_rows', 'normalized_cid'));
    }

    public function test_result_generation_uses_strict_history_service_for_active_d7_context(): void
    {
        $context = $this->createActiveD7Context();
        $targetRowId = DB::table('target_group_rows')->insertGetId([
            'target_group_job_id' => $context['job_id'],
            'target_group_file_id' => $context['file_id'],
            'sheet_name' => 'SYNTHETIC',
            'row_number' => 2,
            'raw_payload' => json_encode(['cid' => self::CID, 'full_name' => 'SYN ALPHA']),
            'raw_cid' => self::CID,
            'normalized_cid' => self::CID,
            'cid_status' => 'valid',
            'raw_full_name' => 'SYN ALPHA',
            'normalized_full_name' => 'SYN ALPHA',
            'raw_birth_date' => '1990-01-01',
            'normalized_birth_date' => '1990-01-01',
            'validation_status' => 'valid',
            'matching_key_version' => HistoryReconciliationService::MATCHING_KEY_VERSION,
            'normalization_version' => HistoryReconciliationService::NORMALIZATION_VERSION,
            'validation_version' => HistoryReconciliationService::VALIDATION_VERSION,
            'review_reason' => null,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        DB::table('source_import_jobs')->insert([
            'job_name' => 'SYNTHETIC SOURCE',
            'status' => 'valid',
            'total_files' => 1,
            'total_rows' => 1,
            'valid_rows' => 1,
            'invalid_rows' => 0,
            'review_rows' => 0,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        $sourceJobId = (int) DB::getPdo()->lastInsertId();
        $sourceFileId = DB::table('source_import_files')->insertGetId([
            'source_import_job_id' => $sourceJobId,
            'original_filename' => 'synthetic-source.csv',
            'stored_path' => '__synthetic__',
            'mime_type' => 'text/csv',
            'size_bytes' => 0,
            'sha256' => hash('sha256', 'synthetic-source'),
            'row_count' => 1,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        DB::table('source_import_rows')->insert([
            'source_import_job_id' => $sourceJobId,
            'source_file_id' => $sourceFileId,
            'sheet_name' => 'SYNTHETIC',
            'row_number' => 2,
            'raw_payload' => json_encode(['cid' => self::CID, 'service_key' => 'alpha']),
            'raw_cid' => self::CID,
            'normalized_cid' => self::CID,
            'cid_status' => 'valid',
            'raw_service_text' => 'alpha',
            'normalized_service_key' => 'alpha',
            'normalized_visit_date' => '2026-01-10',
            'validation_status' => 'valid',
            'scope_context_id' => 'SCOPE-0:lineage:'.self::LINEAGE,
            'matching_key_version' => HistoryReconciliationService::MATCHING_KEY_VERSION,
            'normalization_version' => HistoryReconciliationService::NORMALIZATION_VERSION,
            'validation_version' => HistoryReconciliationService::VALIDATION_VERSION,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $drafts = (new ResultGenerationService())->buildDraftsFromTargetGroupJob($context['job_id'], ['alpha']);

        $this->assertCount(1, $drafts);
        $this->assertSame(ResultGenerationService::CATEGORY_HAS_HISTORY, $drafts[0]['result_category']);
        $this->assertSame(['alpha'], $drafts[0]['selected_service_keys']);
        $this->assertSame([$targetRowId], $drafts[0]['target_group_row_ids']);
    }

    private function service(): HistoryReconciliationService
    {
        return new HistoryReconciliationService(new CidValidator());
    }

    private function subject(array $overrides = []): array
    {
        return array_replace([
            'raw_cid' => self::CID,
            'normalized_cid' => self::CID,
            'cid_status' => CidValidator::STATUS_VALID,
            'matching_key_version' => HistoryReconciliationService::MATCHING_KEY_VERSION,
            'normalization_version' => HistoryReconciliationService::NORMALIZATION_VERSION,
            'validation_version' => HistoryReconciliationService::VALIDATION_VERSION,
            'scope_context_id' => self::SCOPE,
            'lineage_id' => self::LINEAGE,
            'active_version_id' => self::VERSION_ID,
            'subject_version_id' => self::VERSION_ID,
            'full_name' => 'SYN ALPHA',
            'birth_date' => '1990-01-01',
        ], $overrides);
    }

    private function history(array $overrides = []): array
    {
        $history = array_replace([
            'source_type' => 'screening_db',
            'source_file_id' => 10,
            'source_row_id' => 11,
            'normalized_cid' => self::CID,
            'matching_key_version' => HistoryReconciliationService::MATCHING_KEY_VERSION,
            'normalization_version' => HistoryReconciliationService::NORMALIZATION_VERSION,
            'validation_version' => HistoryReconciliationService::VALIDATION_VERSION,
            'scope_context_id' => self::SCOPE,
            'lineage_id' => self::LINEAGE,
            'producing_version_id' => self::VERSION_ID,
            'normalized_service_key' => 'alpha',
            'evidence_date' => '2026-01-10',
            'full_name' => 'SYN ALPHA',
            'birth_date' => '1990-01-01',
            'source_payload' => ['synthetic' => true],
            'provenance' => ['table' => 'source_import_rows', 'row_id' => 11],
            'identity_ambiguous' => false,
            'source_conflict' => false,
        ], $overrides);

        $history['provenance']['row_id'] = $history['source_row_id'];

        return $history;
    }

    private function createActiveD7Context(): array
    {
        $now = now();
        $jobId = DB::table('target_group_jobs')->insertGetId([
            'group_name' => 'SYNTHETIC D7 HISTORY',
            'status' => 'active',
            'total_files' => 1,
            'total_rows' => 1,
            'valid_rows' => 1,
            'invalid_rows' => 0,
            'review_rows' => 0,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        $fileId = DB::table('target_group_files')->insertGetId([
            'target_group_job_id' => $jobId,
            'original_filename' => 'synthetic-target.csv',
            'stored_path' => '__synthetic__',
            'mime_type' => 'text/csv',
            'size_bytes' => 0,
            'sha256' => hash('sha256', 'synthetic-target'),
            'row_count' => 1,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('target_group_lineages')->insert([
            'lineage_id' => self::LINEAGE,
            'next_version_number' => 2,
            'active_version_id' => null,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('target_group_file_versions')->insert([
            'id' => self::VERSION_ID,
            'lineage_id' => self::LINEAGE,
            'version_token' => '22222222-2222-4222-8222-222222222222',
            'version_number' => 1,
            'target_group_file_id' => $fileId,
            'target_group_job_id' => $jobId,
            'version_status' => 'ACTIVE',
            'correlation_id' => '33333333-3333-4333-8333-333333333333',
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('target_group_lineages')
            ->where('lineage_id', self::LINEAGE)
            ->update(['active_version_id' => self::VERSION_ID, 'updated_at' => $now]);

        return ['job_id' => $jobId, 'file_id' => $fileId];
    }
}
