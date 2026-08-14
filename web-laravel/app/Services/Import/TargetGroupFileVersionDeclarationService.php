<?php

namespace App\Services\Import;

use App\Models\AuditLog;
use App\Models\TargetGroupFile;
use App\Models\TargetGroupFileVersion;
use App\Models\TargetGroupLineage;
use Carbon\CarbonImmutable;
use DateTimeInterface;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use LogicException;
use Throwable;

final class TargetGroupFileVersionDeclarationService
{
    private TargetGroupVersionAllocationService $allocator;

    public function __construct(?TargetGroupVersionAllocationService $allocator = null)
    {
        $this->allocator = $allocator ?? new TargetGroupVersionAllocationService();
    }

    /**
     * Declare one corrected physical file as a non-active logical candidate.
     *
     * The physical file, job, lineage and predecessor already exist. This
     * service adds only D7 declaration validation, confirmation metadata and
     * the mandatory typed audit event around the existing allocator.
     *
     * @param array{
     *     lineage_id:string,
     *     version_token:string,
     *     target_group_file_id:int,
     *     target_group_job_id:int,
     *     previous_version_id:int,
     *     correction_reason:string,
     *     confirmed_by_user_id:int,
     *     confirmed_at:DateTimeInterface|string,
     *     correlation_id?:string
     * } $declaration
     */
    public function declareCandidate(array $declaration): TargetGroupFileVersion
    {
        $normalized = $this->normalizeDeclaration($declaration);

        return DB::transaction(function () use ($normalized): TargetGroupFileVersion {
            $file = TargetGroupFile::query()->whereKey($normalized['target_group_file_id'])->first();
            if ($file === null) {
                throw new LogicException('PHYSICAL_FILE_NOT_FOUND');
            }

            $this->assertSha($file->sha256);

            $lineage = TargetGroupLineage::query()
                ->where('lineage_id', $normalized['lineage_id'])
                ->lockForUpdate()
                ->first();
            if ($lineage === null) {
                throw new LogicException('LINEAGE_NOT_FOUND');
            }

            $existing = TargetGroupFileVersion::query()
                ->where('version_token', $normalized['version_token'])
                ->lockForUpdate()
                ->first();

            if ($existing !== null) {
                return $this->replayExisting($existing, $normalized, $file);
            }

            if ((int) $file->target_group_job_id !== $normalized['target_group_job_id']) {
                throw new LogicException('PHYSICAL_FILE_JOB_MISMATCH');
            }

            $this->assertCurrentActivePredecessor($lineage, $normalized['previous_version_id']);
            $predecessor = TargetGroupFileVersion::query()
                ->whereKey($normalized['previous_version_id'])
                ->lockForUpdate()
                ->first();
            if ($predecessor === null) {
                throw new LogicException('PREDECESSOR_NOT_FOUND');
            }

            if ((string) $predecessor->lineage_id !== (string) $lineage->lineage_id) {
                throw new LogicException('PREDECESSOR_LINEAGE_MISMATCH');
            }

            if ($predecessor->version_status !== 'ACTIVE') {
                throw new LogicException('PREDECESSOR_NOT_ACTIVE');
            }

            $predecessorFile = TargetGroupFile::query()->whereKey($predecessor->target_group_file_id)->first();
            if ($predecessorFile === null) {
                throw new LogicException('PREDECESSOR_PHYSICAL_FILE_NOT_FOUND');
            }
            $this->assertSha($predecessorFile->sha256);

            if (hash_equals(strtolower((string) $predecessorFile->sha256), strtolower((string) $file->sha256))) {
                throw new LogicException('CORRECTED_SHA_MUST_DIFFER');
            }

            $candidate = $this->allocator->allocate([
                'lineage_id' => $normalized['lineage_id'],
                'version_token' => $normalized['version_token'],
                'target_group_file_id' => $normalized['target_group_file_id'],
                'target_group_job_id' => $normalized['target_group_job_id'],
                'previous_version_id' => $normalized['previous_version_id'],
                'correction_reason' => $normalized['correction_reason'],
                'correlation_id' => $normalized['correlation_id'],
            ]);

            $candidate->forceFill([
                'version_status' => 'CANDIDATE',
                'correction_reason' => $normalized['correction_reason'],
                'confirmed_by_user_id' => $normalized['confirmed_by_user_id'],
                'confirmed_at' => $normalized['confirmed_at'],
            ])->save();

            $this->writeDeclarationAudit($candidate, $normalized, (string) $file->sha256);

            return $candidate->fresh();
        });
    }

    /**
     * @return array{
     *     lineage_id:string,
     *     version_token:string,
     *     target_group_file_id:int,
     *     target_group_job_id:int,
     *     previous_version_id:int,
     *     correction_reason:string,
     *     confirmed_by_user_id:int,
     *     confirmed_at:CarbonImmutable,
     *     correlation_id:string
     * }
     */
    private function normalizeDeclaration(array $declaration): array
    {
        foreach (['lineage_id', 'version_token', 'target_group_file_id', 'target_group_job_id'] as $field) {
            if (! array_key_exists($field, $declaration) || $declaration[$field] === null || $declaration[$field] === '') {
                throw new LogicException("VERSION_DECLARATION_MISSING_{$field}");
            }
        }

        if (! array_key_exists('previous_version_id', $declaration) || $declaration['previous_version_id'] === null) {
            throw new LogicException('PREDECESSOR_REQUIRED');
        }
        if (! array_key_exists('correction_reason', $declaration) || ! is_string($declaration['correction_reason'])) {
            throw new LogicException('CORRECTION_REASON_REQUIRED');
        }
        if (! array_key_exists('confirmed_by_user_id', $declaration) || $declaration['confirmed_by_user_id'] === null) {
            throw new LogicException('CONFIRMED_BY_USER_REQUIRED');
        }
        if (! array_key_exists('confirmed_at', $declaration) || $declaration['confirmed_at'] === null || $declaration['confirmed_at'] === '') {
            throw new LogicException('CONFIRMED_AT_REQUIRED');
        }

        if (! is_string($declaration['lineage_id']) || ! Str::isUuid($declaration['lineage_id'])) {
            throw new LogicException('LINEAGE_ID_INVALID');
        }
        if (! is_string($declaration['version_token']) || ! Str::isUuid($declaration['version_token'])) {
            throw new LogicException('VERSION_TOKEN_INVALID');
        }
        foreach (['target_group_file_id', 'target_group_job_id', 'previous_version_id', 'confirmed_by_user_id'] as $field) {
            if (! is_int($declaration[$field]) || $declaration[$field] < 1) {
                throw new LogicException("{$field}_INVALID");
            }
        }

        $reason = trim($declaration['correction_reason']);
        if ($reason === '') {
            throw new LogicException('CORRECTION_REASON_REQUIRED');
        }
        if (mb_strlen($reason, 'UTF-8') > 64) {
            throw new LogicException('CORRECTION_REASON_TOO_LONG');
        }

        if (! DB::table('users')->where('id', $declaration['confirmed_by_user_id'])->exists()) {
            throw new LogicException('CONFIRMING_USER_NOT_FOUND');
        }

        try {
            $confirmedAt = CarbonImmutable::parse($declaration['confirmed_at']);
        } catch (Throwable) {
            throw new LogicException('CONFIRMED_AT_INVALID');
        }

        $correlationId = $declaration['correlation_id'] ?? (string) Str::uuid();
        if (! is_string($correlationId) || $correlationId === '') {
            throw new LogicException('CORRELATION_ID_INVALID');
        }

        return [
            'lineage_id' => $declaration['lineage_id'],
            'version_token' => $declaration['version_token'],
            'target_group_file_id' => $declaration['target_group_file_id'],
            'target_group_job_id' => $declaration['target_group_job_id'],
            'previous_version_id' => $declaration['previous_version_id'],
            'correction_reason' => $reason,
            'confirmed_by_user_id' => $declaration['confirmed_by_user_id'],
            'confirmed_at' => $confirmedAt,
            'correlation_id' => $correlationId,
        ];
    }

    private function assertCurrentActivePredecessor(TargetGroupLineage $lineage, int $predecessorId): void
    {
        if ($lineage->active_version_id === null) {
            throw new LogicException('PREDECESSOR_NOT_APPLICABLE');
        }
        if ((int) $lineage->active_version_id !== $predecessorId) {
            throw new LogicException('PREDECESSOR_NOT_CURRENT_ACTIVE');
        }
    }

    private function assertSha(?string $sha): void
    {
        if ($sha === null || preg_match('/\A[a-f0-9]{64}\z/i', $sha) !== 1) {
            throw new LogicException('PHYSICAL_SHA_INVALID');
        }
    }

    private function replayExisting(TargetGroupFileVersion $existing, array $declaration, TargetGroupFile $file): TargetGroupFileVersion
    {
        $sameContext = (string) $existing->lineage_id === $declaration['lineage_id']
            && (int) $existing->target_group_file_id === $declaration['target_group_file_id']
            && (int) $existing->target_group_job_id === $declaration['target_group_job_id']
            && (int) $file->target_group_job_id === $declaration['target_group_job_id']
            && (int) $existing->previous_version_id === $declaration['previous_version_id']
            && $existing->version_token === $declaration['version_token']
            && $existing->version_status === 'CANDIDATE'
            && $existing->correction_reason === $declaration['correction_reason']
            && (int) $existing->confirmed_by_user_id === $declaration['confirmed_by_user_id']
            && $existing->confirmed_at?->toDateTimeString() === $declaration['confirmed_at']->toDateTimeString();

        if (! $sameContext) {
            throw new LogicException('VERSION_TOKEN_CONTEXT_CONFLICT');
        }

        $audits = AuditLog::query()
            ->where('action', 'FILE_VERSION_DECLARED')
            ->where('version_id', $existing->getKey())
            ->lockForUpdate()
            ->get();
        if ($audits->count() !== 1) {
            throw new LogicException('DECLARATION_AUDIT_NOT_IDEMPOTENT');
        }

        $payload = $audits->first()->after_payload;
        if (! is_array($payload) || ($payload['physical_sha256'] ?? null) !== (string) $file->sha256) {
            throw new LogicException('VERSION_TOKEN_CONTEXT_CONFLICT');
        }

        return $existing->fresh();
    }

    private function writeDeclarationAudit(TargetGroupFileVersion $candidate, array $declaration, string $physicalSha): void
    {
        AuditLog::query()->create([
            'actor_user_id' => $declaration['confirmed_by_user_id'],
            'action' => 'FILE_VERSION_DECLARED',
            'entity_type' => 'target_group_file_version',
            'entity_id' => $candidate->getKey(),
            'after_payload' => [
                'physical_sha256' => $physicalSha,
                'version_status' => 'CANDIDATE',
            ],
            'created_at' => now(),
            'correlation_id' => $declaration['correlation_id'],
            'target_group_job_id' => $candidate->target_group_job_id,
            'target_group_file_id' => $candidate->target_group_file_id,
            'review_reason_code' => $candidate->correction_reason,
            'lineage_id' => $candidate->lineage_id,
            'version_id' => $candidate->getKey(),
            'version_token' => $candidate->version_token,
            'version_number' => $candidate->version_number,
            'predecessor_version_id' => $candidate->previous_version_id,
        ]);
    }
}
