<?php

namespace App\Services\Review;

use App\Models\TargetGroupRow;
use App\Models\TargetGroupRowReview;
use App\Services\Audit\AuditLogger;
use App\Services\CidValidator;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use InvalidArgumentException;
use LogicException;

final class TargetGroupReviewService
{
    public const STATE_PENDING_VALIDATION = 'PENDING_VALIDATION';
    public const STATE_VALID = 'VALID';
    public const STATE_NEEDS_REVIEW = 'NEEDS_REVIEW';
    public const STATE_APPROVED = 'APPROVED';
    public const STATE_REJECTED = 'REJECTED';

    public const OUTCOME_APPROVED = 'APPROVED';
    public const OUTCOME_REJECTED = 'REJECTED';

    public const MATCHING_KEY_TYPE = 'CID';
    public const MATCHING_KEY_VERSION = 'cid-v1';
    public const NORMALIZATION_VERSION = 'cid-normalization-v1';
    public const VALIDATION_VERSION = 'thai-cid-checkdigit-v1';

    public const AUTHORITATIVE_REASON_CODES = [
        'MISSING_CID',
        'INVALID_CID_FORMAT',
        'INVALID_CID_CHECK_DIGIT',
        'DUPLICATE_WITHIN_FILE',
        'DUPLICATE_WITHIN_BATCH',
        'DUPLICATE_ACROSS_FILES',
        'NAME_CONFLICT',
        'BIRTH_DATE_CONFLICT',
        'PROGRAM_SCOPE_CONFLICT',
        'HOSPITAL_SCOPE_CONFLICT',
        'AMBIGUOUS_HISTORY',
        'CORRECTED_FILE_VERSION',
        'SOURCE_EVIDENCE_CONFLICT',
    ];

    public const FOUNDATION_REASON_CODES = [
        'MISSING_CID',
        'INVALID_CID_FORMAT',
        'INVALID_CID_CHECK_DIGIT',
        'DUPLICATE_WITHIN_FILE',
        'DUPLICATE_WITHIN_BATCH',
        'NAME_CONFLICT',
        'BIRTH_DATE_CONFLICT',
        'AMBIGUOUS_HISTORY',
        'SOURCE_EVIDENCE_CONFLICT',
    ];

    public function __construct(
        private readonly AuditLogger $auditLogger,
        private readonly CidValidator $cidValidator,
    ) {
    }

    public function authoritativeReasonCodes(): array
    {
        return self::AUTHORITATIVE_REASON_CODES;
    }

    public function foundationReasonCodes(): array
    {
        return self::FOUNDATION_REASON_CODES;
    }

    public function isFoundationReason(string $reasonCode): bool
    {
        return in_array($reasonCode, self::FOUNDATION_REASON_CODES, true);
    }

    public function reviewReasonForCid(?string $rawCid): ?string
    {
        $candidate = trim((string) $rawCid);

        if ($candidate === '') {
            return 'MISSING_CID';
        }

        if (preg_match('/^\d{13}$/', $candidate) !== 1) {
            return 'INVALID_CID_FORMAT';
        }

        return $this->cidValidator->validate($candidate)['is_valid']
            ? null
            : 'INVALID_CID_CHECK_DIGIT';
    }

    public function assertScopeSafe(array $context): void
    {
        if (($context['matching_scope'] ?? 'current_import') !== 'current_import') {
            throw new LogicException('D6 automatic matching is restricted to the current import scope.');
        }

        foreach (['program_id', 'hospital_id', 'tenant_id', 'organization_id'] as $scopeKey) {
            if (array_key_exists($scopeKey, $context) && $context[$scopeKey] !== null) {
                throw new LogicException('D6 persisted cross-scope matching is blocked.');
            }
        }
    }

    public function markValid(TargetGroupRow $row, array $context = []): TargetGroupRow
    {
        $this->assertScopeSafe($context);
        $reasonCode = $this->reviewReasonForCid($row->raw_cid ?? $row->normalized_cid);

        if ($reasonCode !== null) {
            return $this->markNeedsReview($row, $reasonCode, $context);
        }

        return DB::transaction(function () use ($row): TargetGroupRow {
            $locked = TargetGroupRow::query()->lockForUpdate()->findOrFail($row->getKey());

            if (in_array($locked->review_status, [self::STATE_APPROVED, self::STATE_REJECTED], true)) {
                throw new LogicException('A terminal review decision cannot be changed automatically.');
            }

            $locked->fill($this->keyMetadata($locked));
            $locked->fill([
                'review_status' => self::STATE_VALID,
                'review_reason_code' => null,
                'review_outcome' => null,
                'reviewed_by' => null,
                'reviewed_at' => null,
                'conflict_flags' => null,
            ]);
            $locked->save();

            return $locked->fresh();
        });
    }

    public function markNeedsReview(TargetGroupRow $row, string $reasonCode, array $context = []): TargetGroupRow
    {
        if (! $this->isFoundationReason($reasonCode)) {
            throw new InvalidArgumentException('The reason code is deferred from the D6 foundation slice.');
        }

        $this->assertScopeSafe($context);

        return DB::transaction(function () use ($row, $reasonCode, $context): TargetGroupRow {
            $locked = TargetGroupRow::query()->lockForUpdate()->findOrFail($row->getKey());
            $this->assertMutableForAutomaticReview($locked);
            $fromStatus = $locked->review_status ?: self::STATE_PENDING_VALIDATION;
            $correlationId = $this->correlationId($context);

            $locked->fill([
                'review_status' => self::STATE_NEEDS_REVIEW,
                'review_reason_code' => $reasonCode,
                'review_outcome' => null,
                'reviewed_by' => null,
                'reviewed_at' => null,
                'conflict_flags' => $context['conflict_flags'] ?? null,
            ]);
            $locked->save();

            $this->appendEvent($locked, $fromStatus, self::STATE_NEEDS_REVIEW, $reasonCode, null, $context, $correlationId);
            $this->auditLogger->log('review_required', 'target_group_row', $locked->id, $this->auditContext(
                $locked,
                $reasonCode,
                null,
                $context,
                $correlationId,
            ));

            return $locked->fresh();
        });
    }

    public function decide(TargetGroupRow $row, string $outcome, string $reasonCode, array $context = []): TargetGroupRow
    {
        if (! in_array($outcome, [self::OUTCOME_APPROVED, self::OUTCOME_REJECTED], true)) {
            throw new InvalidArgumentException('Only APPROVED or REJECTED are foundation outcomes.');
        }

        if (! $this->isFoundationReason($reasonCode)) {
            throw new InvalidArgumentException('The reason code is deferred from the D6 foundation slice.');
        }

        if (! isset($context['actor_user_id']) || ! is_int($context['actor_user_id'])) {
            throw new LogicException('An authorized operator is required for a review decision.');
        }

        $this->assertScopeSafe($context);

        return DB::transaction(function () use ($row, $outcome, $reasonCode, $context): TargetGroupRow {
            $locked = TargetGroupRow::query()->lockForUpdate()->findOrFail($row->getKey());

            if ($locked->review_status !== self::STATE_NEEDS_REVIEW) {
                throw new LogicException('Only NEEDS_REVIEW rows can receive an operator decision.');
            }

            $reviewedAt = now();
            $correlationId = $this->correlationId($context);
            $locked->fill([
                'review_status' => $outcome,
                'review_reason_code' => $reasonCode,
                'review_outcome' => $outcome,
                'reviewed_by' => $context['actor_user_id'],
                'reviewed_at' => $reviewedAt,
                'conflict_flags' => $context['conflict_flags'] ?? $locked->conflict_flags,
            ]);
            $locked->fill($this->keyMetadata($locked));
            $locked->save();

            $this->appendEvent($locked, self::STATE_NEEDS_REVIEW, $outcome, $reasonCode, $outcome, $context, $correlationId, $reviewedAt);
            $this->auditLogger->log(
                strtolower('review_'.$outcome),
                'target_group_row',
                $locked->id,
                $this->auditContext($locked, $reasonCode, $outcome, $context, $correlationId, $reviewedAt),
            );

            return $locked->fresh();
        });
    }

    private function assertMutableForAutomaticReview(TargetGroupRow $row): void
    {
        if (in_array($row->review_status, [self::STATE_APPROVED, self::STATE_REJECTED], true)) {
            throw new LogicException('A terminal review decision cannot be overwritten.');
        }
    }

    private function keyMetadata(TargetGroupRow $row): array
    {
        if ($this->reviewReasonForCid($row->raw_cid ?? $row->normalized_cid) !== null) {
            return [
                'matching_key_type' => null,
                'matching_key_version' => null,
                'normalization_version' => null,
                'validation_version' => self::VALIDATION_VERSION,
            ];
        }

        return [
            'matching_key_type' => self::MATCHING_KEY_TYPE,
            'matching_key_version' => self::MATCHING_KEY_VERSION,
            'normalization_version' => self::NORMALIZATION_VERSION,
            'validation_version' => self::VALIDATION_VERSION,
        ];
    }

    private function appendEvent(
        TargetGroupRow $row,
        string $fromStatus,
        string $toStatus,
        string $reasonCode,
        ?string $outcome,
        array $context,
        string $correlationId,
        mixed $reviewedAt = null,
    ): void {
        TargetGroupRowReview::query()->create([
            'target_group_job_id' => $row->target_group_job_id,
            'target_group_file_id' => $row->target_group_file_id,
            'target_group_row_id' => $row->id,
            'reviewed_by' => $context['actor_user_id'] ?? null,
            'correlation_id' => $correlationId,
            'from_status' => $fromStatus,
            'to_status' => $toStatus,
            'review_outcome' => $outcome,
            'review_reason_code' => $reasonCode,
            'matching_key_type' => $row->matching_key_type,
            'matching_key_version' => $row->matching_key_version,
            'normalization_version' => $row->normalization_version,
            'validation_version' => $row->validation_version,
            'conflict_flags' => $context['conflict_flags'] ?? $row->conflict_flags,
            'evidence_references' => $context['evidence_references'] ?? $this->evidenceReferences($row),
            'operator_note' => $context['operator_note'] ?? null,
            'reviewed_at' => $reviewedAt,
            'created_at' => now(),
        ]);
    }

    private function auditContext(
        TargetGroupRow $row,
        string $reasonCode,
        ?string $outcome,
        array $context,
        string $correlationId,
        mixed $reviewedAt = null,
    ): array {
        return [
            'actor_user_id' => $context['actor_user_id'] ?? null,
            'ip_address' => $context['ip_address'] ?? null,
            'user_agent' => $context['user_agent'] ?? null,
            'correlation_id' => $correlationId,
            'target_group_job_id' => $row->target_group_job_id,
            'target_group_file_id' => $row->target_group_file_id,
            'target_group_row_id' => $row->id,
            'matching_key_type' => $row->matching_key_type,
            'matching_key_version' => $row->matching_key_version,
            'review_reason_code' => $reasonCode,
            'review_outcome' => $outcome,
            'conflict_flags' => $context['conflict_flags'] ?? $row->conflict_flags,
            'reviewed_by' => $context['actor_user_id'] ?? null,
            'reviewed_at' => $reviewedAt,
            'after_payload' => [
                'review_status' => $row->review_status,
                'review_reason_code' => $reasonCode,
                'review_outcome' => $outcome,
                'evidence_references' => $context['evidence_references'] ?? $this->evidenceReferences($row),
            ],
        ];
    }

    private function evidenceReferences(TargetGroupRow $row): array
    {
        return [
            'target_group_job_id' => $row->target_group_job_id,
            'target_group_file_id' => $row->target_group_file_id,
            'target_group_row_id' => $row->id,
        ];
    }

    private function correlationId(array $context): string
    {
        $candidate = $context['correlation_id'] ?? null;

        if (is_string($candidate) && trim($candidate) !== '' && strlen($candidate) <= 64) {
            return $candidate;
        }

        return (string) Str::uuid();
    }
}
