<?php

namespace App\Services\Import;

use App\Models\AuditLog;
use App\Models\TargetGroupFileVersion;
use App\Models\TargetGroupLineage;
use App\Models\TargetGroupVersionSupersession;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use LogicException;

final class TargetGroupFileVersionActivationService
{
    public function activate(array $activation): array
    {
        $input = $this->normalize($activation);
        return DB::transaction(function () use ($input): array {
            $lineage = TargetGroupLineage::query()->where('lineage_id', $input['lineage_id'])->lockForUpdate()->first();
            if ($lineage === null) throw new LogicException('LINEAGE_NOT_FOUND');
            if ($lineage->active_version_id === null) throw new LogicException('ROOT_ACTIVATION_NOT_AUTHORIZED');
            if (TargetGroupFileVersion::query()->where('lineage_id', $lineage->lineage_id)->where('version_status', 'ACTIVE')->count() !== 1) throw new LogicException('CORRUPT_ACTIVE_STATE');
            $predecessor = TargetGroupFileVersion::query()->whereKey($input['expected_predecessor_version_id'])->lockForUpdate()->first();
            if ($predecessor === null) throw new LogicException('PREDECESSOR_NOT_FOUND');
            if ((int) $predecessor->getKey() === $input['candidate_version_id']) throw new LogicException('CANDIDATE_PREDECESSOR_SAME');
            $candidate = TargetGroupFileVersion::query()->whereKey($input['candidate_version_id'])->lockForUpdate()->first();
            if ($candidate === null) throw new LogicException('CANDIDATE_NOT_FOUND');
            $this->assertSameLineage($lineage, $predecessor, $candidate);
            if ((int) $candidate->previous_version_id !== (int) $predecessor->getKey()) throw new LogicException('CANDIDATE_PREDECESSOR_MISMATCH');
            $preRelations = TargetGroupVersionSupersession::query()->where('predecessor_version_id', $predecessor->getKey())->lockForUpdate()->get();
            $candidateRelations = TargetGroupVersionSupersession::query()->where(function ($q) use ($candidate): void { $q->where('successor_version_id', $candidate->getKey())->orWhere('predecessor_version_id', $candidate->getKey()); })->lockForUpdate()->get();
            $relatedAudits = AuditLog::query()->where('action', 'VERSION_SUPERSEDED')->where(function ($q) use ($predecessor, $candidate): void { $q->where('predecessor_version_id', $predecessor->getKey())->orWhere('successor_version_id', $candidate->getKey())->orWhere('version_id', $candidate->getKey()); })->lockForUpdate()->get();
            $exactRelation = $preRelations->count() === 1 && (int) $preRelations->first()->successor_version_id === (int) $candidate->getKey() && $candidateRelations->count() === 1 && (int) $candidateRelations->first()->predecessor_version_id === (int) $predecessor->getKey();
            $exactAudits = AuditLog::query()->where('action', 'VERSION_SUPERSEDED')->where('lineage_id', $lineage->lineage_id)->where('predecessor_version_id', $predecessor->getKey())->where('successor_version_id', $candidate->getKey())->where('version_id', $candidate->getKey())->lockForUpdate()->get();
            if ($candidate->version_status === 'ACTIVE' && (int) $lineage->active_version_id === (int) $candidate->getKey() && $predecessor->version_status === 'SUPERSEDED' && $exactRelation && $exactAudits->count() === 1 && $relatedAudits->count() === 1) return ['result' => 'AUTHORITATIVE_ALREADY_COMMITTED_REPLAY', 'version' => $candidate->fresh()];
            if ((int) $lineage->active_version_id === (int) $candidate->getKey() || $candidate->version_status === 'ACTIVE' || $predecessor->version_status === 'SUPERSEDED' || $preRelations->isNotEmpty() || $candidateRelations->isNotEmpty() || $relatedAudits->isNotEmpty()) throw new LogicException('CORRUPT_ACTIVE_STATE');
            if ((int) $lineage->active_version_id !== (int) $predecessor->getKey()) throw new LogicException('PREDECESSOR_NOT_CURRENT_ACTIVE');
            if ($predecessor->version_status !== 'ACTIVE') throw new LogicException('CORRUPT_ACTIVE_STATE');
            if ($candidate->version_status !== 'CANDIDATE') throw new LogicException('CANDIDATE_NOT_ELIGIBLE');
            if (!DB::table('users')->where('id', $input['actor_user_id'])->exists()) throw new LogicException('ACTOR_NOT_FOUND');
            $reason = trim((string) $candidate->correction_reason);
            if ($reason === '' || mb_strlen($reason, 'UTF-8') > 64) throw new LogicException('CORRECTION_REASON_REQUIRED');
            $now = now();
            $predecessor->forceFill(['version_status' => 'SUPERSEDED','superseded_by_id' => $candidate->getKey(),'superseded_at' => $now,'superseded_by_user_id' => $input['actor_user_id'],'supersession_reason' => $reason])->save();
            $candidate->forceFill(['version_status' => 'ACTIVE'])->save();
            TargetGroupVersionSupersession::query()->create(['predecessor_version_id' => $predecessor->getKey(),'successor_version_id' => $candidate->getKey(),'committed_by_user_id' => $input['actor_user_id'],'correlation_id' => $input['correlation_id'],'supersession_reason' => $reason,'committed_at' => $now]);
            $lineage->forceFill(['active_version_id' => $candidate->getKey()])->save();
            AuditLog::query()->create(['actor_user_id' => $input['actor_user_id'],'action' => 'VERSION_SUPERSEDED','entity_type' => 'target_group_file_version','entity_id' => $candidate->getKey(),'before_payload' => ['active_version_id' => $predecessor->getKey(),'predecessor_version_id' => $predecessor->getKey(),'successor_version_id' => $candidate->getKey(),'predecessor_version_token' => $predecessor->version_token,'successor_version_token' => $candidate->version_token,'predecessor_version_number' => $predecessor->version_number,'successor_version_number' => $candidate->version_number,'predecessor_version_status' => 'ACTIVE','successor_version_status' => 'CANDIDATE'],'after_payload' => ['active_version_id' => $candidate->getKey(),'predecessor_version_id' => $predecessor->getKey(),'successor_version_id' => $candidate->getKey(),'predecessor_version_token' => $predecessor->version_token,'successor_version_token' => $candidate->version_token,'predecessor_version_number' => $predecessor->version_number,'successor_version_number' => $candidate->version_number,'predecessor_version_status' => 'SUPERSEDED','successor_version_status' => 'ACTIVE','correction_reason' => $reason],'created_at' => $now,'correlation_id' => $input['correlation_id'],'target_group_job_id' => $candidate->target_group_job_id,'target_group_file_id' => $candidate->target_group_file_id,'review_reason_code' => $reason,'lineage_id' => $lineage->lineage_id,'version_id' => $candidate->getKey(),'version_token' => $candidate->version_token,'version_number' => $candidate->version_number,'predecessor_version_id' => $predecessor->getKey(),'successor_version_id' => $candidate->getKey()]);
            return ['result' => 'ACTIVATED', 'version' => $candidate->fresh()];
        });
    }
    private function normalize(array $activation): array
    {
        foreach (['lineage_id','candidate_version_id','expected_predecessor_version_id','actor_user_id'] as $field) if (!array_key_exists($field, $activation) || $activation[$field] === null || $activation[$field] === '') throw new LogicException("ACTIVATION_MISSING_{$field}");
        if (!is_string($activation['lineage_id']) || !Str::isUuid($activation['lineage_id'])) throw new LogicException('LINEAGE_ID_INVALID');
        foreach (['candidate_version_id','expected_predecessor_version_id','actor_user_id'] as $field) if (!is_int($activation[$field]) || $activation[$field] < 1) throw new LogicException("{$field}_INVALID");
        $correlation = $activation['correlation_id'] ?? (string) Str::uuid();
        if (!is_string($correlation) || !Str::isUuid($correlation)) throw new LogicException('CORRELATION_ID_INVALID');
        return ['lineage_id' => $activation['lineage_id'],'candidate_version_id' => $activation['candidate_version_id'],'expected_predecessor_version_id' => $activation['expected_predecessor_version_id'],'actor_user_id' => $activation['actor_user_id'],'correlation_id' => $correlation];
    }
    private function assertSameLineage(TargetGroupLineage $lineage, TargetGroupFileVersion $predecessor, TargetGroupFileVersion $candidate): void
    {
        if ((string) $predecessor->lineage_id !== (string) $lineage->lineage_id) throw new LogicException('PREDECESSOR_LINEAGE_MISMATCH');
        if ((string) $candidate->lineage_id !== (string) $lineage->lineage_id) throw new LogicException('CANDIDATE_LINEAGE_MISMATCH');
    }
}
