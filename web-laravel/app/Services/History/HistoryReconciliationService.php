<?php

namespace App\Services\History;

use App\Services\CidValidator;
use App\Services\Result\ResultGenerationService;
use App\Services\Review\TargetGroupReviewService;

final class HistoryReconciliationService
{
    public const MATCHING_KEY_TYPE = TargetGroupReviewService::MATCHING_KEY_TYPE;
    public const MATCHING_KEY_VERSION = TargetGroupReviewService::MATCHING_KEY_VERSION;
    public const NORMALIZATION_VERSION = TargetGroupReviewService::NORMALIZATION_VERSION;
    public const VALIDATION_VERSION = TargetGroupReviewService::VALIDATION_VERSION;

    /**
     * Reconcile one accepted, version-bound subject against already bounded evidence.
     *
     * The caller must supply evidence from the current SCOPE-0 context. This service
     * deliberately does not query a global history corpus or infer program/hospital scope.
     */
    public function __construct(private readonly CidValidator $cidValidator = new CidValidator())
    {
    }

    public function reconcile(array $subject, array $historyRows, array $selectedServiceKeys): array
    {
        $identifier = $this->cidValidator->validate($subject['raw_cid'] ?? null);
        $selectedServices = $this->selectedServices($selectedServiceKeys);

        if (! $identifier['is_valid']) {
            return $this->reviewDecision(
                null,
                $this->identityReason($identifier['status'], $subject['raw_cid'] ?? null),
            );
        }

        if (! $this->authoritativeSubjectIdentity($subject, $identifier)
            || ! $this->authoritativeActiveVersion($subject)
            || ! $this->hasScope($subject)) {
            return $this->reviewDecision($identifier['normalized_cid'], 'AMBIGUOUS_HISTORY');
        }

        $relevantRows = [];
        $unresolvedRows = false;

        foreach ($historyRows as $historyRow) {
            if (($historyRow['normalized_cid'] ?? null) !== $identifier['normalized_cid']) {
                continue;
            }

            if (! isset($selectedServices[(string) ($historyRow['normalized_service_key'] ?? '')])) {
                continue;
            }

            if (($historyRow['scope_context_id'] ?? null) !== $subject['scope_context_id']) {
                if (($historyRow['scope_context_id'] ?? null) === null) {
                    $unresolvedRows = true;
                }
                continue;
            }

            if (! $this->authoritativeHistoryIdentity($historyRow)
                || ! $this->compatibleLineage($subject, $historyRow)
                || ! $this->producingVersionIsBound($historyRow)) {
                $unresolvedRows = true;
                continue;
            }

            $relevantRows[] = $historyRow;
        }

        if ($unresolvedRows) {
            return $this->reviewDecision(
                $identifier['normalized_cid'],
                'AMBIGUOUS_HISTORY',
                $this->evidenceSummary($relevantRows),
            );
        }

        foreach ($relevantRows as $historyRow) {
            if ($this->isSourceConflict($historyRow)) {
                return $this->reviewDecision(
                    $identifier['normalized_cid'],
                    'SOURCE_EVIDENCE_CONFLICT',
                    $this->evidenceSummary($relevantRows),
                );
            }

            if ($this->isIdentityAmbiguous($historyRow)) {
                return $this->reviewDecision(
                    $identifier['normalized_cid'],
                    'AMBIGUOUS_HISTORY',
                    $this->evidenceSummary($relevantRows),
                );
            }

            $identityConflict = $this->identityConflict($subject, $historyRow);
            if ($identityConflict !== null) {
                return $this->reviewDecision(
                    $identifier['normalized_cid'],
                    $identityConflict,
                    $this->evidenceSummary($relevantRows),
                );
            }
        }

        $evidenceSummary = $this->evidenceSummary($relevantRows);
        $latest = $this->latest($relevantRows);
        $hasHistory = $relevantRows !== [];

        return [
            'person_key' => 'cid:'.$identifier['normalized_cid'],
            'normalized_cid' => $identifier['normalized_cid'],
            'identifier_status' => CidValidator::STATUS_VALID,
            'result_category' => $hasHistory
                ? ResultGenerationService::CATEGORY_HAS_HISTORY
                : ResultGenerationService::CATEGORY_NO_HISTORY,
            'has_screening_db_history' => $this->hasSourceType($relevantRows, 'screening_db'),
            'has_target_group_file_history' => $this->hasSourceType($relevantRows, 'target_group_file'),
            'has_any_history' => $hasHistory,
            'latest_history_date' => $latest['evidence_date'] ?? null,
            'latest_history_source' => $latest['source_type'] ?? null,
            'selected_service_keys' => array_keys($selectedServices),
            'evidence_summary' => $evidenceSummary,
            'review_status' => 'not_required',
            'review_reason' => null,
        ];
    }

    private function authoritativeSubjectIdentity(array $subject, array $identifier): bool
    {
        return ($subject['cid_status'] ?? null) === CidValidator::STATUS_VALID
            && ($subject['normalized_cid'] ?? null) === $identifier['normalized_cid']
            && ($subject['matching_key_version'] ?? null) === self::MATCHING_KEY_VERSION
            && ($subject['normalization_version'] ?? null) === self::NORMALIZATION_VERSION
            && ($subject['validation_version'] ?? null) === self::VALIDATION_VERSION;
    }

    private function authoritativeHistoryIdentity(array $historyRow): bool
    {
        return ($historyRow['matching_key_version'] ?? null) === self::MATCHING_KEY_VERSION
            && ($historyRow['normalization_version'] ?? null) === self::NORMALIZATION_VERSION
            && ($historyRow['validation_version'] ?? null) === self::VALIDATION_VERSION;
    }

    private function authoritativeActiveVersion(array $subject): bool
    {
        return isset($subject['lineage_id'], $subject['active_version_id'], $subject['subject_version_id'])
            && $subject['lineage_id'] !== ''
            && $subject['active_version_id'] !== null
            && (int) $subject['active_version_id'] > 0
            && (int) $subject['subject_version_id'] === (int) $subject['active_version_id'];
    }

    private function hasScope(array $subject): bool
    {
        return isset($subject['scope_context_id'])
            && is_string($subject['scope_context_id'])
            && trim($subject['scope_context_id']) !== '';
    }

    private function compatibleLineage(array $subject, array $historyRow): bool
    {
        $historyLineage = $historyRow['lineage_id'] ?? null;

        return $historyLineage === null || $historyLineage === $subject['lineage_id'];
    }

    private function producingVersionIsBound(array $historyRow): bool
    {
        if (($historyRow['source_type'] ?? null) !== 'target_group_file') {
            return true;
        }

        return isset($historyRow['producing_version_id'])
            && (int) $historyRow['producing_version_id'] > 0;
    }

    private function selectedServices(array $selectedServiceKeys): array
    {
        $services = [];

        foreach ($selectedServiceKeys as $serviceKey) {
            $normalized = trim((string) $serviceKey);
            if ($normalized !== '') {
                $services[$normalized] = true;
            }
        }

        return $services;
    }

    private function identityReason(string $status, ?string $rawCid): string
    {
        if ($status === CidValidator::STATUS_MISSING) {
            return 'MISSING_CID';
        }

        if (preg_match('/^\d{13}$/', trim((string) $rawCid)) !== 1) {
            return 'INVALID_CID_FORMAT';
        }

        return 'INVALID_CID_CHECK_DIGIT';
    }

    private function identityConflict(array $subject, array $historyRow): ?string
    {
        $subjectName = trim((string) ($subject['full_name'] ?? ''));
        $historyName = trim((string) ($historyRow['full_name'] ?? ''));
        if ($subjectName !== '' && $historyName !== '' && $subjectName !== $historyName) {
            return 'NAME_CONFLICT';
        }

        $subjectBirthDate = (string) ($subject['birth_date'] ?? '');
        $historyBirthDate = (string) ($historyRow['birth_date'] ?? '');
        if ($subjectBirthDate !== '' && $historyBirthDate !== '' && $subjectBirthDate !== $historyBirthDate) {
            return 'BIRTH_DATE_CONFLICT';
        }

        return null;
    }

    private function isSourceConflict(array $historyRow): bool
    {
        return ($historyRow['source_conflict'] ?? false) === true
            || (($historyRow['provenance']['source_conflict'] ?? false) === true);
    }

    private function isIdentityAmbiguous(array $historyRow): bool
    {
        return ($historyRow['identity_ambiguous'] ?? false) === true
            || (($historyRow['provenance']['identity_ambiguous'] ?? false) === true);
    }

    private function reviewDecision(?string $normalizedCid, string $reason, array $evidenceSummary = ['sources' => []]): array
    {
        return [
            'person_key' => $normalizedCid !== null ? 'cid:'.$normalizedCid : 'unresolved',
            'normalized_cid' => $normalizedCid,
            'identifier_status' => $normalizedCid === null ? CidValidator::STATUS_MISSING : CidValidator::STATUS_INVALID,
            'result_category' => ResultGenerationService::CATEGORY_NEEDS_REVIEW,
            'has_screening_db_history' => false,
            'has_target_group_file_history' => false,
            'has_any_history' => false,
            'latest_history_date' => null,
            'latest_history_source' => null,
            'selected_service_keys' => [],
            'evidence_summary' => $evidenceSummary,
            'review_status' => 'needs_review',
            'review_reason' => $reason,
        ];
    }

    private function evidenceSummary(array $historyRows): array
    {
        return [
            'sources' => array_values(array_map(
                fn (array $row): array => [
                    'source_type' => $row['source_type'] ?? null,
                    'source_file_id' => $row['source_file_id'] ?? null,
                    'sheet_name' => $row['sheet_name'] ?? null,
                    'row_number' => $row['row_number'] ?? null,
                    'source_payload' => $this->privacySafePayload($row['source_payload'] ?? []),
                    'normalized_service_key' => $row['normalized_service_key'] ?? null,
                    'evidence_date' => $row['evidence_date'] ?? null,
                    'provenance' => $row['provenance'] ?? [],
                ],
                $historyRows,
            )),
        ];
    }

    private function privacySafePayload(mixed $payload): mixed
    {
        if (! is_array($payload)) {
            return $payload;
        }

        $safe = [];
        foreach ($payload as $key => $value) {
            $normalizedKey = strtolower((string) $key);
            if (str_contains($normalizedKey, 'cid')
                || str_contains($normalizedKey, 'name')
                || str_contains($normalizedKey, 'birth')) {
                continue;
            }
            $safe[$key] = is_array($value) ? $this->privacySafePayload($value) : $value;
        }

        return $safe;
    }

    private function latest(array $historyRows): ?array
    {
        usort(
            $historyRows,
            fn (array $left, array $right): int => strcmp(
                (string) ($right['evidence_date'] ?? ''),
                (string) ($left['evidence_date'] ?? ''),
            ),
        );

        return $historyRows[0] ?? null;
    }

    private function hasSourceType(array $historyRows, string $sourceType): bool
    {
        foreach ($historyRows as $historyRow) {
            if (($historyRow['source_type'] ?? null) === $sourceType) {
                return true;
            }
        }

        return false;
    }
}
