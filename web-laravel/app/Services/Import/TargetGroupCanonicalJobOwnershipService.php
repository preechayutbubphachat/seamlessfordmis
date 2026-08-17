<?php

namespace App\Services\Import;

use App\Models\AuditLog;
use App\Models\TargetGroupFileVersion;
use App\Models\TargetGroupImportRequest;
use App\Models\TargetGroupJob;
use App\Models\TargetGroupLineage;
use App\Models\TargetGroupVersionSupersession;
use App\Services\Audit\AuditLogger;
use Illuminate\Database\UniqueConstraintViolationException;
use Illuminate\Support\Facades\DB;
use LogicException;
use Throwable;

final class TargetGroupCanonicalJobOwnershipService
{
    private const JOB_GROUP_NAME = 'D7_ACTIVATION';
    private const JOB_RECEIVED = 'RECEIVED';

    public function __construct(
        private readonly TargetGroupImportRequestIdempotencyService $requestRegistration = new TargetGroupImportRequestIdempotencyService(),
        private readonly AuditLogger $auditLogger = new AuditLogger(),
    ) {
    }

    /**
     * Resolve one D7 request to its single canonical job without executing D7.
     *
     * @return array{state:string,request:TargetGroupImportRequest,job:?TargetGroupJob,canonical_job_id:?int,reason:?string,result:?array<string,mixed>}
     */
    public function register(array $input): array
    {
        $request = $this->requestRegistration->registerD7Activation($input);

        try {
            return DB::transaction(function () use ($request, $input): array {
                $lockedRequest = TargetGroupImportRequest::query()
                    ->whereKey($request->getKey())
                    ->lockForUpdate()
                    ->first();

                if ($lockedRequest === null) {
                    return $this->unknown(null, null, 'REQUEST_NOT_FOUND');
                }

                $hadCanonicalOwner = $lockedRequest->canonical_job_id !== null
                    || TargetGroupJob::query()->where('import_request_id', $lockedRequest->getKey())->exists();
                $job = $this->resolveCanonicalJob($lockedRequest);
                $outcome = $this->classify($lockedRequest, $job, $input);
                $this->auditOutcome($outcome, $lockedRequest, $job, $hadCanonicalOwner);

                return $this->result($outcome['state'], $lockedRequest, $job, $outcome['reason'], $outcome['result']);
            });
        } catch (UniqueConstraintViolationException) {
            return $this->reconcileJobCollision($request, $input);
        } catch (LogicException $exception) {
            if ($exception->getMessage() !== 'CANONICAL_JOB_BINDING_CONFLICT') {
                throw $exception;
            }

            $freshRequest = TargetGroupImportRequest::query()->whereKey($request->getKey())->first();
            $job = $freshRequest?->canonical_job_id === null
                ? null
                : TargetGroupJob::query()->whereKey($freshRequest->canonical_job_id)->first();

            $this->auditBindingConflict($freshRequest, $job);

            return $this->unknown($freshRequest ?? $request, $job, 'CANONICAL_JOB_BINDING_CONFLICT');
        } catch (Throwable) {
            return $this->unknown($request, null, 'RECONCILIATION_REQUIRED');
        }
    }

    private function resolveCanonicalJob(TargetGroupImportRequest $request): TargetGroupJob
    {
        $requestJobs = TargetGroupJob::query()
            ->where('import_request_id', $request->getKey())
            ->lockForUpdate()
            ->get();

        if ($requestJobs->count() > 1) {
            throw new LogicException('CANONICAL_JOB_BINDING_CONFLICT');
        }

        if ($request->canonical_job_id !== null) {
            $job = TargetGroupJob::query()
                ->whereKey($request->canonical_job_id)
                ->lockForUpdate()
                ->first();

            if ($job === null || (string) $job->import_request_id !== (string) $request->getKey()) {
                throw new LogicException('CANONICAL_JOB_BINDING_CONFLICT');
            }

            if ($requestJobs->isNotEmpty() && (int) $requestJobs->first()->getKey() !== (int) $job->getKey()) {
                throw new LogicException('CANONICAL_JOB_BINDING_CONFLICT');
            }

            return $job;
        }

        if ($requestJobs->isNotEmpty()) {
            $job = $requestJobs->first();
            DB::table('import_requests')
                ->where('import_request_id', $request->getKey())
                ->update(['canonical_job_id' => $job->getKey()]);

            return $request->fresh()->canonicalJob()->lockForUpdate()->firstOrFail();
        }

        $job = TargetGroupJob::query()->create([
            'created_by_user_id' => $request->created_by_user_id,
            'group_name' => self::JOB_GROUP_NAME,
            'status' => self::JOB_RECEIVED,
            'import_request_id' => $request->getKey(),
        ]);

        DB::table('import_requests')
            ->where('import_request_id', $request->getKey())
            ->update(['canonical_job_id' => $job->getKey()]);

        return TargetGroupJob::query()
            ->whereKey($job->getKey())
            ->lockForUpdate()
            ->firstOrFail();
    }

    /**
     * @return array{state:string,reason:?string,result:?array<string,mixed>}
     */
    private function classify(TargetGroupImportRequest $request, TargetGroupJob $job, array $input): array
    {
        $evidence = $this->committedEvidence($job, $input);
        if ($evidence['state'] === 'COMMITTED') {
            return $evidence;
        }
        if ($evidence['state'] === 'CONFLICT') {
            return ['state' => 'OUTCOME_UNKNOWN', 'reason' => 'RECONCILIATION_REQUIRED', 'result' => null];
        }

        $requestState = strtoupper((string) $request->lifecycle_state);
        $jobState = strtoupper((string) $job->status);
        $states = [$requestState, $jobState];

        if (array_intersect($states, ['OUTCOME_UNKNOWN', 'UNKNOWN', 'RECONCILIATION_REQUIRED', 'CONFLICT']) !== []) {
            return ['state' => 'OUTCOME_UNKNOWN', 'reason' => 'RECONCILIATION_REQUIRED', 'result' => null];
        }

        if (array_intersect($states, ['COMMITTED', 'COMPLETED', 'SUCCEEDED']) !== []) {
            return ['state' => 'OUTCOME_UNKNOWN', 'reason' => 'COMMITTED_EVIDENCE_MISSING', 'result' => null];
        }

        if (array_intersect($states, ['FAILED', 'FAILED_BEFORE_COMMIT', 'FAILED_FINAL', 'FAILED_RETRYABLE']) !== []) {
            return ['state' => 'FAILED_BEFORE_COMMIT', 'reason' => $request->failure_code ?? $job->error_message, 'result' => null];
        }

        if (array_intersect($states, ['PROCESSING', 'IN_PROGRESS', 'RUNNING', 'STARTED']) !== []) {
            return ['state' => 'IN_PROGRESS', 'reason' => null, 'result' => null];
        }

        if (array_intersect($states, ['PENDING', 'RECEIVED', 'CREATED', 'QUEUED']) !== []) {
            return ['state' => 'NOT_STARTED', 'reason' => null, 'result' => null];
        }

        return ['state' => 'OUTCOME_UNKNOWN', 'reason' => 'RECONCILIATION_REQUIRED', 'result' => null];
    }

    /**
     * @return array{state:string,reason:?string,result:?array<string,mixed>}
     */
    private function committedEvidence(TargetGroupJob $job, array $input): array
    {
        $lineage = TargetGroupLineage::query()->where('lineage_id', $input['lineage_id'])->first();
        $candidate = TargetGroupFileVersion::query()->whereKey($input['candidate_version_id'])->first();
        $predecessor = TargetGroupFileVersion::query()->whereKey($input['expected_predecessor_version_id'])->first();
        $relation = TargetGroupVersionSupersession::query()
            ->where('predecessor_version_id', $input['expected_predecessor_version_id'])
            ->where('successor_version_id', $input['candidate_version_id'])
            ->first();
        $auditExists = AuditLog::query()
            ->where('action', 'VERSION_SUPERSEDED')
            ->where('lineage_id', $input['lineage_id'])
            ->where('version_id', $input['candidate_version_id'])
            ->where('predecessor_version_id', $input['expected_predecessor_version_id'])
            ->where('successor_version_id', $input['candidate_version_id'])
            ->exists();

        $committedMarkerExists = ($lineage !== null && (int) $lineage->active_version_id === (int) $input['candidate_version_id'])
            || ($candidate !== null && $candidate->version_status === 'ACTIVE')
            || ($predecessor !== null && $predecessor->version_status === 'SUPERSEDED')
            || $relation !== null
            || $auditExists;
        if (! $committedMarkerExists) {
            return ['state' => 'NONE', 'reason' => null, 'result' => null];
        }

        $committed = $lineage !== null
            && (int) $lineage->active_version_id === (int) $input['candidate_version_id']
            && $candidate !== null
            && (int) $candidate->target_group_job_id === (int) $job->getKey()
            && (string) $candidate->lineage_id === (string) $input['lineage_id']
            && $candidate->version_status === 'ACTIVE'
            && (int) $candidate->previous_version_id === (int) $input['expected_predecessor_version_id']
            && $predecessor !== null
            && $predecessor->version_status === 'SUPERSEDED'
            && (int) $predecessor->superseded_by_id === (int) $candidate->getKey()
            && $relation !== null
            && $auditExists;

        if (! $committed) {
            return ['state' => 'CONFLICT', 'reason' => 'RECONCILIATION_REQUIRED', 'result' => null];
        }

        return [
            'state' => 'COMMITTED',
            'reason' => null,
            'result' => [
                'result' => 'AUTHORITATIVE_COMMITTED_REPLAY',
                'lineage_id' => $input['lineage_id'],
                'predecessor_version_id' => (int) $predecessor->getKey(),
                'successor_version_id' => (int) $candidate->getKey(),
            ],
        ];
    }

    /**
     * @return array{state:string,request:TargetGroupImportRequest,job:?TargetGroupJob,canonical_job_id:?int,reason:?string,result:?array<string,mixed>}
     */
    private function result(string $state, TargetGroupImportRequest $request, ?TargetGroupJob $job, ?string $reason, ?array $result): array
    {
        return [
            'state' => $state,
            'request' => $request->fresh(),
            'job' => $job?->fresh(),
            'canonical_job_id' => $job?->getKey() ?? $request->canonical_job_id,
            'reason' => $reason,
            'result' => $result,
        ];
    }

    /**
     * @return array{state:string,request:TargetGroupImportRequest,job:?TargetGroupJob,canonical_job_id:?int,reason:?string,result:null}
     */
    private function unknown(?TargetGroupImportRequest $request, ?TargetGroupJob $job, string $reason): array
    {
        $request ??= new TargetGroupImportRequest();

        return [
            'state' => 'OUTCOME_UNKNOWN',
            'request' => $request,
            'job' => $job,
            'canonical_job_id' => $job?->getKey() ?? $request->canonical_job_id,
            'reason' => $reason,
            'result' => null,
        ];
    }

    private function auditOutcome(array $outcome, TargetGroupImportRequest $request, TargetGroupJob $job, bool $hadCanonicalOwner): void
    {
        $action = $outcome['state'] === 'NOT_STARTED' && ! $hadCanonicalOwner
            ? 'CANONICAL_JOB_REGISTERED'
            : 'CANONICAL_JOB_REPLAYED';

        $this->auditLogger->log($action, 'target_group_job', null, [
            'import_request_id' => $request->getKey(),
            'target_group_job_id' => $job->getKey(),
            'correlation_id' => $request->correlation_id,
            'reconciliation_outcome' => $outcome['state'],
            'after_payload' => ['state' => $outcome['state']],
        ]);
    }

    private function auditBindingConflict(?TargetGroupImportRequest $request, ?TargetGroupJob $job): void
    {
        $this->auditLogger->log('CANONICAL_JOB_BINDING_CONFLICT', 'target_group_job', null, [
            'import_request_id' => $request?->getKey(),
            'target_group_job_id' => $job?->getKey(),
            'correlation_id' => $request?->correlation_id,
            'conflict_code' => 'CANONICAL_JOB_BINDING_CONFLICT',
            'reconciliation_outcome' => 'RECONCILIATION_REQUIRED',
        ]);
    }

    /**
     * @return array{state:string,request:TargetGroupImportRequest,job:?TargetGroupJob,canonical_job_id:?int,reason:?string,result:?array<string,mixed>}
     */
    private function reconcileJobCollision(TargetGroupImportRequest $request, array $input): array
    {
        try {
            return DB::transaction(function () use ($request, $input): array {
                $lockedRequest = TargetGroupImportRequest::query()
                    ->whereKey($request->getKey())
                    ->lockForUpdate()
                    ->first();

                if ($lockedRequest === null) {
                    return $this->unknown($request, null, 'RECONCILIATION_REQUIRED');
                }

                $job = $this->resolveCanonicalJob($lockedRequest);
                $outcome = $this->classify($lockedRequest, $job, $input);

                return $this->result($outcome['state'], $lockedRequest, $job, $outcome['reason'], $outcome['result']);
            });
        } catch (Throwable) {
            return $this->unknown($request, null, 'RECONCILIATION_REQUIRED');
        }
    }
}
