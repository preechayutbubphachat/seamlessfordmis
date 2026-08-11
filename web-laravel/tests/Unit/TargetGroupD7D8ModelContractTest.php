<?php

namespace Tests\Unit;

use App\Models\AuditLog;
use App\Models\ImportContentObject;
use App\Models\TargetGroupFile;
use App\Models\TargetGroupFileVersion;
use App\Models\TargetGroupImportRequest;
use App\Models\TargetGroupJob;
use App\Models\TargetGroupJobAttempt;
use App\Models\TargetGroupLineage;
use App\Models\TargetGroupVersionSupersession;
use Tests\TestCase;

final class TargetGroupD7D8ModelContractTest extends TestCase
{
    public function test_foundation_models_have_exact_table_and_identity_mapping(): void
    {
        $this->assertSame('import_content_objects', (new ImportContentObject())->getTable());
        $this->assertSame('import_requests', (new TargetGroupImportRequest())->getTable());
        $this->assertSame('import_request_id', (new TargetGroupImportRequest())->getKeyName());
        $this->assertFalse((new TargetGroupImportRequest())->getIncrementing());
        $this->assertSame('target_group_job_attempts', (new TargetGroupJobAttempt())->getTable());
        $this->assertSame('attempt_id', (new TargetGroupJobAttempt())->getKeyName());
        $this->assertSame('target_group_lineages', (new TargetGroupLineage())->getTable());
        $this->assertSame('lineage_id', (new TargetGroupLineage())->getKeyName());
        $this->assertSame('target_group_file_versions', (new TargetGroupFileVersion())->getTable());
        $this->assertSame('target_group_version_supersessions', (new TargetGroupVersionSupersession())->getTable());
    }

    public function test_relationships_expose_only_structural_foundation_links(): void
    {
        $this->assertSame('target_group_files', (new ImportContentObject())->targetGroupFiles()->getRelated()->getTable());
        $this->assertSame('target_group_jobs', (new TargetGroupImportRequest())->jobs()->getRelated()->getTable());
        $this->assertSame('target_group_jobs', (new TargetGroupJobAttempt())->job()->getRelated()->getTable());
        $this->assertSame('target_group_file_versions', (new TargetGroupLineage())->versions()->getRelated()->getTable());
        $this->assertSame('target_group_lineages', (new TargetGroupFileVersion())->lineage()->getRelated()->getTable());
        $this->assertSame('target_group_version_supersessions', (new TargetGroupFileVersion())->supersessionAsPredecessor()->getRelated()->getTable());
        $this->assertSame('import_requests', (new TargetGroupJob())->importRequest()->getRelated()->getTable());
        $this->assertSame('import_content_objects', (new TargetGroupFile())->contentObject()->getRelated()->getTable());
        $this->assertSame('target_group_file_versions', (new AuditLog())->version()->getRelated()->getTable());
    }

    public function test_models_have_identity_fields_but_no_runtime_execution_methods(): void
    {
        $this->assertContains('sha256', (new ImportContentObject())->getFillable());
        $this->assertContains('import_request_id', (new TargetGroupImportRequest())->getFillable());
        $this->assertContains('attempt_number', (new TargetGroupJobAttempt())->getFillable());
        $this->assertContains('next_version_number', (new TargetGroupLineage())->getFillable());
        $this->assertContains('version_token', (new TargetGroupFileVersion())->getFillable());
        $this->assertContains('predecessor_version_id', (new TargetGroupVersionSupersession())->getFillable());
        $this->assertContains('content_object_id', (new TargetGroupFile())->getFillable());
        $this->assertContains('lineage_id', (new AuditLog())->getFillable());

        foreach ([
            ImportContentObject::class,
            TargetGroupImportRequest::class,
            TargetGroupJobAttempt::class,
            TargetGroupLineage::class,
            TargetGroupFileVersion::class,
            TargetGroupVersionSupersession::class,
            TargetGroupJob::class,
            TargetGroupFile::class,
            AuditLog::class,
        ] as $model) {
            $instance = new $model();
            $this->assertFalse(method_exists($instance, 'stage'));
            $this->assertFalse(method_exists($instance, 'process'));
            $this->assertFalse(method_exists($instance, 'retryImport'));
            $this->assertFalse(method_exists($instance, 'activateSuccessor'));
        }
    }
}
