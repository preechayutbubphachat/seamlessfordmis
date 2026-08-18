<?php

namespace App\Services\Result;

use App\Services\CidValidator;
use App\Services\History\HistoryReconciliationService;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;
use LogicException;

final class ResultGenerationService
{
    public const CATEGORY_HAS_HISTORY = 'has_history';
    public const CATEGORY_NO_HISTORY = 'no_history';
    public const CATEGORY_INVALID_IDENTIFIER = 'invalid_identifier';
    public const CATEGORY_MISSING_IDENTIFIER = 'missing_identifier';
    public const CATEGORY_NEEDS_REVIEW = 'needs_review';

    public function __construct(
        private readonly CidValidator $cidValidator = new CidValidator(),
        private readonly HistoryReconciliationService $historyReconciliationService = new HistoryReconciliationService(),
    )
    {
    }

    public function generate(int $targetGroupJobId, array $selectedServiceKeys): array
    {
        throw new LogicException('Database-backed W5 result generation is not implemented.');
    }

    public function buildDraftsFromTargetGroupJob(int $targetGroupJobId, array $selectedServiceKeys): array
    {
        $targetRows = DB::table('target_group_rows')
            ->where('target_group_job_id', $targetGroupJobId)
            ->orderBy('row_number')
            ->get();

        $groups = [];

        foreach ($targetRows as $row) {
            $identifierStatus = (string) $row->cid_status;
            $personKey = $row->normalized_cid !== null && $identifierStatus === CidValidator::STATUS_VALID
                ? 'cid:'.$row->normalized_cid
                : 'target-row:'.$row->id;

            $groups[$personKey][] = $row;
        }

        $drafts = [];

        foreach ($groups as $personKey => $rows) {
            $primaryRow = $rows[0];
            $targetRow = $this->targetRowToDraftInput($primaryRow);
            $targetRow['identity_ambiguous'] = $this->hasAmbiguousIdentity($rows);

            $activeVersionContext = $this->activeVersionContext($primaryRow);
            if ($activeVersionContext !== null) {
                $historyRows = array_merge(
                    $this->strictSourceHistoryForTargetRow($primaryRow, $activeVersionContext),
                    $this->strictTargetGroupFileHistoryForRows($targetGroupJobId, $rows, $activeVersionContext),
                );
                $draft = $this->historyReconciliationService->reconcile(
                    $this->targetRowToHistorySubject($primaryRow, $activeVersionContext),
                    $historyRows,
                    $selectedServiceKeys,
                );
            } else {
                $historyRows = array_merge(
                    $this->sourceHistoryForTargetRow($primaryRow),
                    $this->targetGroupFileHistoryForRows($targetGroupJobId, $rows),
                );
                $draft = $this->buildPersonResultDraft($targetRow, $historyRows, $selectedServiceKeys);
            }

            if ($activeVersionContext === null) {
                $draft['person_key'] = $personKey;
            } else {
                $draft['person_key'] = $draft['person_key'] ?? $personKey;
            }
            $draft['display_name'] = $primaryRow->normalized_full_name ?? $primaryRow->raw_full_name;
            $draft['review_status'] = $draft['result_category'] === self::CATEGORY_NEEDS_REVIEW ? 'needs_review' : 'not_required';
            $draft['review_reason'] = $draft['result_category'] === self::CATEGORY_NEEDS_REVIEW
                ? ($draft['review_reason'] ?? 'AMBIGUOUS_HISTORY')
                : null;
            $draft['target_group_row_ids'] = array_map(fn (object $row): int => (int) $row->id, $rows);

            $drafts[] = $draft;
        }

        return $drafts;
    }

    public function persistResultDraftsForJob(int $targetGroupJobId, array $drafts, array $context = []): array
    {
        return DB::transaction(function () use ($targetGroupJobId, $drafts, $context): array {
            foreach ($drafts as $draft) {
                $this->validatePersistableDraft($draft);
            }

            $selectedServiceKeys = array_values($context['selected_service_keys'] ?? []);
            $now = now();
            $existingJob = DB::table('result_generation_jobs')
                ->where('target_group_job_id', $targetGroupJobId)
                ->first();

            if ($existingJob !== null) {
                DB::table('target_group_results')
                    ->where('result_generation_job_id', $existingJob->id)
                    ->delete();

                DB::table('result_generation_jobs')
                    ->where('id', $existingJob->id)
                    ->update([
                        'status' => 'drafted',
                        'selected_service_keys' => json_encode($selectedServiceKeys),
                        'normalization_version' => (int) ($context['normalization_version'] ?? 1),
                        'source_set_hash' => $context['source_set_hash'] ?? null,
                        'total_persons' => count($drafts),
                        'completed_persons' => count($drafts),
                        'error_message' => null,
                        'started_at' => $now,
                        'finished_at' => $now,
                        'updated_at' => $now,
                    ]);

                $resultGenerationJobId = (int) $existingJob->id;
            } else {
                $resultGenerationJobId = (int) DB::table('result_generation_jobs')->insertGetId([
                    'target_group_job_id' => $targetGroupJobId,
                    'created_by_user_id' => $context['created_by_user_id'] ?? null,
                    'status' => 'drafted',
                    'selected_service_keys' => json_encode($selectedServiceKeys),
                    'normalization_version' => (int) ($context['normalization_version'] ?? 1),
                    'source_set_hash' => $context['source_set_hash'] ?? null,
                    'total_persons' => count($drafts),
                    'completed_persons' => count($drafts),
                    'error_message' => null,
                    'started_at' => $now,
                    'finished_at' => $now,
                    'created_at' => $now,
                    'updated_at' => $now,
                ]);
            }

            foreach ($drafts as $draft) {
                $resultId = (int) DB::table('target_group_results')->insertGetId([
                    'target_group_job_id' => $targetGroupJobId,
                    'result_generation_job_id' => $resultGenerationJobId,
                    'normalized_cid' => $draft['normalized_cid'] ?? null,
                    'person_key' => $draft['person_key'],
                    'display_name' => $draft['display_name'] ?? null,
                    'result_category' => $draft['result_category'],
                    'has_screening_db_history' => (bool) ($draft['has_screening_db_history'] ?? false),
                    'has_target_group_file_history' => (bool) ($draft['has_target_group_file_history'] ?? false),
                    'has_any_history' => (bool) ($draft['has_any_history'] ?? false),
                    'latest_history_date' => $draft['latest_history_date'] ?? null,
                    'latest_history_source' => $draft['latest_history_source'] ?? null,
                    'selected_service_keys' => json_encode(array_values($draft['selected_service_keys'] ?? $selectedServiceKeys)),
                    'evidence_summary' => json_encode($draft['evidence_summary'] ?? ['sources' => []]),
                    'review_status' => $draft['review_status'] ?? 'not_required',
                    'review_reason' => $draft['review_reason'] ?? null,
                    'created_at' => $now,
                    'updated_at' => $now,
                ]);

                foreach (($draft['evidence_summary']['sources'] ?? []) as $source) {
                    DB::table('target_group_result_sources')->insert([
                        'target_group_result_id' => $resultId,
                        'source_type' => $source['source_type'],
                        'source_file_id' => $source['source_file_id'] ?? null,
                        'sheet_name' => $source['sheet_name'] ?? null,
                        'row_number' => $source['row_number'] ?? null,
                        'source_payload' => json_encode($source['source_payload'] ?? []),
                        'evidence_date' => $source['evidence_date'] ?? null,
                        'normalized_service_key' => $source['normalized_service_key'] ?? null,
                        'provenance' => json_encode($source['provenance'] ?? []),
                        'created_at' => $now,
                        'updated_at' => $now,
                    ]);
                }
            }

            return [
                'result_generation_job_id' => $resultGenerationJobId,
                'persisted_results' => count($drafts),
            ];
        });
    }

    /**
     * @return array{is_valid: bool, status: string, normalized_cid: ?string}
     */
    public function classifyIdentifierStatus(?string $rawCid): array
    {
        return $this->cidValidator->validate($rawCid);
    }

    public function summarizeHistoryEvidence(array $historyRows, array $selectedServiceKeys): array
    {
        $matchingRows = $this->filterHistoryBySelectedServices($historyRows, $selectedServiceKeys);

        return [
            'sources' => array_values(array_map(
                fn (array $row): array => [
                    'source_type' => $row['source_type'] ?? null,
                    'source_file_id' => $row['source_file_id'] ?? null,
                    'sheet_name' => $row['sheet_name'] ?? null,
                    'row_number' => $row['row_number'] ?? null,
                    'source_payload' => $row['source_payload'] ?? [],
                    'normalized_service_key' => $row['normalized_service_key'] ?? null,
                    'evidence_date' => $row['evidence_date'] ?? null,
                    'provenance' => $row['provenance'] ?? [],
                ],
                $matchingRows
            )),
        ];
    }

    public function selectLatestHistoryForServices(array $historyRows, array $selectedServiceKeys): ?array
    {
        $matchingRows = $this->filterHistoryBySelectedServices($historyRows, $selectedServiceKeys);

        usort(
            $matchingRows,
            fn (array $left, array $right): int => strcmp((string) ($right['evidence_date'] ?? ''), (string) ($left['evidence_date'] ?? ''))
        );

        return $matchingRows[0] ?? null;
    }

    public function buildPersonResultDraft(array $targetRow, array $historyRows, array $selectedServiceKeys): array
    {
        $identifier = $this->classifyIdentifierStatus($targetRow['raw_cid'] ?? null);
        $matchingHistoryRows = $this->filterHistoryBySelectedServices($historyRows, $selectedServiceKeys);
        $latestHistory = $this->selectLatestHistoryForServices($historyRows, $selectedServiceKeys);
        $evidenceSummary = $this->summarizeHistoryEvidence($historyRows, $selectedServiceKeys);
        $hasScreeningDbHistory = $this->hasSourceType($matchingHistoryRows, 'screening_db');
        $hasTargetGroupFileHistory = $this->hasSourceType($matchingHistoryRows, 'target_group_file');
        $hasAnyHistory = $hasScreeningDbHistory || $hasTargetGroupFileHistory;

        return [
            'person_key' => $identifier['normalized_cid'] ?? 'unresolved',
            'normalized_cid' => $identifier['normalized_cid'],
            'identifier_status' => $identifier['status'],
            'result_category' => $this->resultCategory($identifier['status'], $hasAnyHistory, (bool) ($targetRow['identity_ambiguous'] ?? false)),
            'has_screening_db_history' => $hasScreeningDbHistory,
            'has_target_group_file_history' => $hasTargetGroupFileHistory,
            'has_any_history' => $hasAnyHistory,
            'latest_history_date' => $latestHistory['evidence_date'] ?? null,
            'latest_history_source' => $latestHistory['source_type'] ?? null,
            'selected_service_keys' => array_values($selectedServiceKeys),
            'evidence_summary' => $evidenceSummary,
            'raw_payload' => $targetRow['raw_payload'] ?? [],
        ];
    }

    private function filterHistoryBySelectedServices(array $historyRows, array $selectedServiceKeys): array
    {
        $selected = array_fill_keys($selectedServiceKeys, true);

        return array_values(array_filter(
            $historyRows,
            fn (array $row): bool => isset($selected[$row['normalized_service_key'] ?? null])
        ));
    }

    private function targetRowToDraftInput(object $row): array
    {
        return [
            'raw_cid' => $row->raw_cid,
            'raw_payload' => json_decode((string) $row->raw_payload, true) ?: [],
        ];
    }

    private function hasAmbiguousIdentity(array $rows): bool
    {
        if (count($rows) < 2) {
            return false;
        }

        $names = [];

        foreach ($rows as $row) {
            $name = trim((string) ($row->normalized_full_name ?? $row->raw_full_name ?? ''));

            if ($name !== '') {
                $names[$name] = true;
            }
        }

        return count($names) > 1;
    }

    private function activeVersionContext(object $targetRow): ?array
    {
        $version = DB::table('target_group_file_versions as versions')
            ->join('target_group_lineages as lineages', 'lineages.active_version_id', '=', 'versions.id')
            ->where('versions.target_group_job_id', $targetRow->target_group_job_id)
            ->where('versions.target_group_file_id', $targetRow->target_group_file_id)
            ->where('versions.version_status', 'ACTIVE')
            ->first([
                'versions.id as active_version_id',
                'versions.lineage_id',
            ]);

        if ($version === null) {
            return null;
        }

        return [
            'active_version_id' => (int) $version->active_version_id,
            'lineage_id' => (string) $version->lineage_id,
            'scope_context_id' => 'SCOPE-0:lineage:'.$version->lineage_id,
        ];
    }

    private function targetRowToHistorySubject(object $targetRow, array $versionContext): array
    {
        return [
            'raw_cid' => $targetRow->raw_cid,
            'normalized_cid' => $targetRow->normalized_cid,
            'cid_status' => $targetRow->cid_status,
            'matching_key_version' => $targetRow->matching_key_version,
            'normalization_version' => $targetRow->normalization_version,
            'validation_version' => $targetRow->validation_version,
            'scope_context_id' => $versionContext['scope_context_id'],
            'lineage_id' => $versionContext['lineage_id'],
            'active_version_id' => $versionContext['active_version_id'],
            'subject_version_id' => $versionContext['active_version_id'],
            'full_name' => $targetRow->normalized_full_name ?? $targetRow->raw_full_name,
            'birth_date' => $targetRow->normalized_birth_date,
        ];
    }

    private function strictSourceHistoryForTargetRow(object $targetRow, array $versionContext): array
    {
        if ($targetRow->normalized_cid === null) {
            return [];
        }

        return DB::table('source_import_rows')
            ->where('scope_context_id', $versionContext['scope_context_id'])
            ->where('normalized_cid', $targetRow->normalized_cid)
            ->orderBy('row_number')
            ->get()
            ->map(fn (object $row): array => [
                'source_type' => 'screening_db',
                'source_file_id' => $row->source_file_id !== null ? (int) $row->source_file_id : null,
                'sheet_name' => $row->sheet_name,
                'row_number' => $row->row_number,
                'source_payload' => json_decode((string) $row->raw_payload, true) ?: [],
                'evidence_date' => $row->normalized_visit_date,
                'normalized_service_key' => $row->normalized_service_key,
                'normalized_cid' => $row->normalized_cid,
                'matching_key_version' => $row->matching_key_version,
                'normalization_version' => $row->normalization_version,
                'validation_version' => $row->validation_version,
                'scope_context_id' => $row->scope_context_id,
                'full_name' => $row->normalized_full_name ?? $row->raw_full_name,
                'birth_date' => null,
                'provenance' => [
                    'table' => 'source_import_rows',
                    'row_id' => (int) $row->id,
                    'source_import_job_id' => (int) $row->source_import_job_id,
                    'source_file_id' => $row->source_file_id !== null ? (int) $row->source_file_id : null,
                ],
            ])
            ->all();
    }

    private function strictTargetGroupFileHistoryForRows(int $targetGroupJobId, array $targetRows, array $versionContext): array
    {
        $targetRowIds = array_map(fn (object $row): int => (int) $row->id, $targetRows);

        return DB::table('target_group_history_rows')
            ->where('target_group_job_id', $targetGroupJobId)
            ->whereIn('target_group_row_id', $targetRowIds)
            ->orderBy('row_number')
            ->get()
            ->map(fn (object $row): array => [
                'source_type' => 'target_group_file',
                'source_file_id' => $row->target_group_file_id !== null ? (int) $row->target_group_file_id : null,
                'sheet_name' => $row->sheet_name,
                'row_number' => $row->row_number,
                'source_payload' => json_decode((string) $row->raw_payload, true) ?: [],
                'evidence_date' => $row->normalized_visit_date,
                'normalized_service_key' => $row->normalized_service_key,
                'normalized_cid' => $row->normalized_cid,
                'matching_key_version' => $row->matching_key_version,
                'normalization_version' => $row->normalization_version,
                'validation_version' => $row->validation_version,
                'scope_context_id' => $row->scope_context_id,
                'lineage_id' => $versionContext['lineage_id'],
                'producing_version_id' => $row->target_group_file_version_id,
                'full_name' => null,
                'birth_date' => null,
                'provenance' => json_decode((string) $row->provenance, true) ?: [],
            ])
            ->all();
    }

    private function sourceHistoryForTargetRow(object $targetRow): array
    {
        if ($targetRow->normalized_cid === null) {
            return [];
        }

        return DB::table('source_import_rows')
            ->where('normalized_cid', $targetRow->normalized_cid)
            ->orderBy('row_number')
            ->get()
            ->map(fn (object $row): array => [
                'source_type' => 'screening_db',
                'source_file_id' => (int) $row->source_file_id,
                'sheet_name' => $row->sheet_name,
                'row_number' => $row->row_number,
                'source_payload' => json_decode((string) $row->raw_payload, true) ?: [],
                'evidence_date' => $row->normalized_visit_date,
                'normalized_service_key' => $row->normalized_service_key,
                'provenance' => [
                    'table' => 'source_import_rows',
                    'row_id' => (int) $row->id,
                    'source_import_job_id' => (int) $row->source_import_job_id,
                    'source_file_id' => (int) $row->source_file_id,
                ],
            ])
            ->all();
    }

    private function targetGroupFileHistoryForRows(int $targetGroupJobId, array $targetRows): array
    {
        $targetRowIds = array_map(fn (object $row): int => (int) $row->id, $targetRows);

        return DB::table('target_group_history_rows')
            ->where('target_group_job_id', $targetGroupJobId)
            ->whereIn('target_group_row_id', $targetRowIds)
            ->orderBy('row_number')
            ->get()
            ->map(fn (object $row): array => [
                'source_type' => 'target_group_file',
                'source_file_id' => $row->target_group_file_id !== null ? (int) $row->target_group_file_id : null,
                'sheet_name' => $row->sheet_name,
                'row_number' => $row->row_number,
                'source_payload' => json_decode((string) $row->raw_payload, true) ?: [],
                'evidence_date' => $row->normalized_visit_date,
                'normalized_service_key' => $row->normalized_service_key,
                'provenance' => [
                    'table' => 'target_group_history_rows',
                    'row_id' => (int) $row->id,
                    'target_group_job_id' => (int) $row->target_group_job_id,
                    'target_group_row_id' => $row->target_group_row_id !== null ? (int) $row->target_group_row_id : null,
                    'target_group_file_id' => $row->target_group_file_id !== null ? (int) $row->target_group_file_id : null,
                ],
            ])
            ->all();
    }

    private function hasSourceType(array $historyRows, string $sourceType): bool
    {
        foreach ($historyRows as $row) {
            if (($row['source_type'] ?? null) === $sourceType) {
                return true;
            }
        }

        return false;
    }

    private function resultCategory(string $identifierStatus, bool $hasAnyHistory, bool $identityAmbiguous): string
    {
        if ($identifierStatus === CidValidator::STATUS_MISSING) {
            return self::CATEGORY_MISSING_IDENTIFIER;
        }

        if ($identifierStatus === CidValidator::STATUS_INVALID) {
            return self::CATEGORY_INVALID_IDENTIFIER;
        }

        if ($identityAmbiguous) {
            return self::CATEGORY_NEEDS_REVIEW;
        }

        return $hasAnyHistory ? self::CATEGORY_HAS_HISTORY : self::CATEGORY_NO_HISTORY;
    }

    private function validatePersistableDraft(array $draft): void
    {
        foreach (['person_key', 'result_category'] as $requiredField) {
            if (!array_key_exists($requiredField, $draft) || $draft[$requiredField] === '') {
                throw new InvalidArgumentException("Result draft is missing {$requiredField}.");
            }
        }

        if (!in_array($draft['result_category'], [
            self::CATEGORY_HAS_HISTORY,
            self::CATEGORY_NO_HISTORY,
            self::CATEGORY_INVALID_IDENTIFIER,
            self::CATEGORY_MISSING_IDENTIFIER,
            self::CATEGORY_NEEDS_REVIEW,
        ], true)) {
            throw new InvalidArgumentException('Result draft has unsupported result_category.');
        }

        foreach (($draft['evidence_summary']['sources'] ?? []) as $source) {
            if (empty($source['source_type'])) {
                throw new InvalidArgumentException('Result source is missing source_type.');
            }
        }
    }
}
