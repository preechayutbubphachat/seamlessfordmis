<?php

namespace App\Services\Import;

use App\Models\TargetGroupFile;
use App\Models\TargetGroupFileVersion;
use App\Models\TargetGroupLineage;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use LogicException;

final class TargetGroupVersionAllocationService
{
    /**
     * Allocate one D7 candidate version from an already-persisted physical file.
     *
     * @param array{
     *     lineage_id:string,
     *     version_token:string,
     *     target_group_file_id:int,
     *     target_group_job_id:int,
     *     previous_version_id?:int|null,
     *     correction_reason:string,
     *     correlation_id?:string
     * } $declaration
     */
    public function allocate(array $declaration): TargetGroupFileVersion
    {
        $this->validateDeclaration($declaration);

        return DB::transaction(function () use ($declaration): TargetGroupFileVersion {
            $lineage = TargetGroupLineage::query()
                ->whereKey($declaration['lineage_id'])
                ->lockForUpdate()
                ->firstOrFail();

            $existing = TargetGroupFileVersion::query()
                ->where('version_token', $declaration['version_token'])
                ->first();

            if ($existing !== null) {
                $this->assertReplayContext($existing, $declaration);

                return $existing->fresh();
            }

            $file = TargetGroupFile::query()
                ->whereKey($declaration['target_group_file_id'])
                ->where('target_group_job_id', $declaration['target_group_job_id'])
                ->firstOrFail();

            $nextVersionNumber = (int) $lineage->next_version_number;
            if ($nextVersionNumber < 1) {
                throw new LogicException('LINEAGE_VERSION_COUNTER_INVALID');
            }

            $previousVersionId = $declaration['previous_version_id'] ?? null;
            if ($previousVersionId !== null) {
                $previous = TargetGroupFileVersion::query()
                    ->whereKey($previousVersionId)
                    ->lockForUpdate()
                    ->firstOrFail();

                if ((string) $previous->lineage_id !== (string) $lineage->lineage_id) {
                    throw new LogicException('PREDECESSOR_LINEAGE_MISMATCH');
                }

                if ((int) $previous->version_number >= $nextVersionNumber) {
                    throw new LogicException('PREDECESSOR_VERSION_NOT_BEFORE_CANDIDATE');
                }
            }

            $lineage->next_version_number = $nextVersionNumber + 1;
            $lineage->save();

            return TargetGroupFileVersion::query()->create([
                'lineage_id' => $lineage->lineage_id,
                'version_token' => $declaration['version_token'],
                'version_number' => $nextVersionNumber,
                'target_group_file_id' => $file->getKey(),
                'target_group_job_id' => $file->target_group_job_id,
                'previous_version_id' => $previousVersionId,
                'version_status' => 'CANDIDATE',
                'correction_reason' => $declaration['correction_reason'],
                'correlation_id' => $declaration['correlation_id'] ?? (string) Str::uuid(),
            ]);
        });
    }

    private function validateDeclaration(array $declaration): void
    {
        foreach (['lineage_id', 'version_token', 'target_group_file_id', 'target_group_job_id', 'correction_reason'] as $field) {
            if (! array_key_exists($field, $declaration) || $declaration[$field] === '') {
                throw new LogicException("VERSION_DECLARATION_MISSING_{$field}");
            }
        }

        if (! is_string($declaration['lineage_id']) || ! Str::isUuid($declaration['lineage_id'])) {
            throw new LogicException('LINEAGE_ID_INVALID');
        }

        if (! is_string($declaration['version_token']) || ! Str::isUuid($declaration['version_token'])) {
            throw new LogicException('VERSION_TOKEN_INVALID');
        }

        if (! is_int($declaration['target_group_file_id']) || ! is_int($declaration['target_group_job_id']) || ! is_string($declaration['correction_reason'])) {
            throw new LogicException('VERSION_DECLARATION_TYPES_INVALID');
        }

        if (array_key_exists('previous_version_id', $declaration) && $declaration['previous_version_id'] !== null && ! is_int($declaration['previous_version_id'])) {
            throw new LogicException('PREDECESSOR_VERSION_ID_INVALID');
        }
    }

    private function assertReplayContext(TargetGroupFileVersion $existing, array $declaration): void
    {
        $sameContext = (string) $existing->lineage_id === (string) $declaration['lineage_id']
            && (int) $existing->target_group_file_id === $declaration['target_group_file_id']
            && (int) $existing->target_group_job_id === $declaration['target_group_job_id']
            && $existing->previous_version_id === ($declaration['previous_version_id'] ?? null)
            && $existing->correction_reason === $declaration['correction_reason']
            && $existing->version_status === 'CANDIDATE';

        if (! $sameContext) {
            throw new LogicException('VERSION_TOKEN_CONTEXT_CONFLICT');
        }
    }
}
