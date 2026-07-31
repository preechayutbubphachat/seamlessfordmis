<?php

namespace Tests\Unit;

use App\Models\AuditLog;
use App\Models\SourceImportFile;
use App\Models\SourceImportJob;
use App\Models\SourceImportRow;
use App\Models\TargetGroupFile;
use App\Models\TargetGroupHistoryRow;
use App\Models\TargetGroupJob;
use App\Models\TargetGroupRow;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Tests\TestCase;

final class ImportStagingModelContractTest extends TestCase
{
    public function test_source_import_models_expose_staging_columns_and_relationships(): void
    {
        $job = new SourceImportJob();
        $file = new SourceImportFile();
        $row = new SourceImportRow();

        $this->assertContains('job_name', $job->getFillable());
        $this->assertContains('sha256', $file->getFillable());
        $this->assertContains('raw_payload', $row->getFillable());
        $this->assertContains('normalized_service_key', $row->getFillable());
        $this->assertSame('array', $row->getCasts()['raw_payload']);

        $this->assertInstanceOf(HasMany::class, $job->files());
        $this->assertInstanceOf(HasMany::class, $job->rows());
        $this->assertInstanceOf(BelongsTo::class, $file->job());
        $this->assertInstanceOf(HasMany::class, $file->rows());
        $this->assertInstanceOf(BelongsTo::class, $row->job());
        $this->assertInstanceOf(BelongsTo::class, $row->file());
    }

    public function test_target_group_models_expose_staging_and_history_contracts(): void
    {
        $job = new TargetGroupJob();
        $file = new TargetGroupFile();
        $row = new TargetGroupRow();
        $history = new TargetGroupHistoryRow();

        foreach (['raw_payload', 'raw_cid', 'normalized_cid', 'cid_status', 'raw_full_name', 'normalized_full_name', 'raw_birth_date', 'normalized_birth_date', 'validation_status', 'review_reason'] as $field) {
            $this->assertContains($field, $row->getFillable());
        }

        foreach (['raw_payload', 'raw_service_text', 'normalized_service_key', 'raw_visit_date', 'normalized_visit_date', 'evidence_source', 'provenance'] as $field) {
            $this->assertContains($field, $history->getFillable());
        }

        $this->assertSame('array', $row->getCasts()['raw_payload']);
        $this->assertSame('array', $history->getCasts()['raw_payload']);
        $this->assertSame('array', $history->getCasts()['provenance']);
        $this->assertInstanceOf(HasMany::class, $job->files());
        $this->assertInstanceOf(HasMany::class, $job->rows());
        $this->assertInstanceOf(HasMany::class, $job->historyRows());
        $this->assertInstanceOf(BelongsTo::class, $file->job());
        $this->assertInstanceOf(HasMany::class, $file->rows());
        $this->assertInstanceOf(HasMany::class, $file->historyRows());
        $this->assertInstanceOf(BelongsTo::class, $row->job());
        $this->assertInstanceOf(BelongsTo::class, $row->file());
        $this->assertInstanceOf(HasMany::class, $row->historyRows());
        $this->assertInstanceOf(BelongsTo::class, $history->job());
        $this->assertInstanceOf(BelongsTo::class, $history->row());
        $this->assertInstanceOf(BelongsTo::class, $history->file());
    }

    public function test_audit_log_model_exposes_payload_casts_and_actor_relationship(): void
    {
        $auditLog = new AuditLog();

        $this->assertContains('before_payload', $auditLog->getFillable());
        $this->assertContains('after_payload', $auditLog->getFillable());
        $this->assertSame('array', $auditLog->getCasts()['before_payload']);
        $this->assertSame('array', $auditLog->getCasts()['after_payload']);
        $this->assertInstanceOf(BelongsTo::class, $auditLog->actor());
    }
}
