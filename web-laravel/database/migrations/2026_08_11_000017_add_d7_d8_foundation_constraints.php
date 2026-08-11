<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('import_requests', function (Blueprint $table): void {
            $table->foreign('canonical_job_id', 'import_requests_canonical_job_foreign')
                ->references('id')->on('target_group_jobs')->restrictOnDelete();
            $table->foreign('created_by_user_id', 'import_requests_created_by_user_foreign')
                ->references('id')->on('users')->nullOnDelete();
        });

        Schema::table('target_group_jobs', function (Blueprint $table): void {
            $table->foreign('import_request_id', 'target_group_jobs_import_request_foreign')
                ->references('import_request_id')->on('import_requests')->restrictOnDelete();
            $table->foreign('retry_of_job_id', 'target_group_jobs_retry_of_job_foreign')
                ->references('id')->on('target_group_jobs')->restrictOnDelete();
            $table->unique('import_request_id', 'target_group_jobs_import_request_unique');
        });

        Schema::table('target_group_files', function (Blueprint $table): void {
            $table->foreign('content_object_id', 'target_group_files_content_object_foreign')
                ->references('id')->on('import_content_objects')->restrictOnDelete();
            $table->unique(['target_group_job_id', 'content_object_id'], 'target_group_files_job_content_unique');
        });

        Schema::table('target_group_lineages', function (Blueprint $table): void {
            $table->foreign('active_version_id', 'target_group_lineages_active_version_foreign')
                ->references('id')->on('target_group_file_versions')->restrictOnDelete();
        });

        Schema::table('audit_logs', function (Blueprint $table): void {
            $table->foreign('import_request_id', 'audit_logs_import_request_foreign')
                ->references('import_request_id')->on('import_requests')->restrictOnDelete();
            $table->foreign('content_object_id', 'audit_logs_content_object_foreign')
                ->references('id')->on('import_content_objects')->restrictOnDelete();
            $table->foreign('attempt_id', 'audit_logs_attempt_foreign')
                ->references('attempt_id')->on('target_group_job_attempts')->restrictOnDelete();
            $table->foreign('lineage_id', 'audit_logs_lineage_foreign')
                ->references('lineage_id')->on('target_group_lineages')->restrictOnDelete();
            $table->foreign('version_id', 'audit_logs_version_foreign')
                ->references('id')->on('target_group_file_versions')->restrictOnDelete();
            $table->foreign('predecessor_version_id', 'audit_logs_predecessor_version_foreign')
                ->references('id')->on('target_group_file_versions')->restrictOnDelete();
            $table->foreign('successor_version_id', 'audit_logs_successor_version_foreign')
                ->references('id')->on('target_group_file_versions')->restrictOnDelete();
        });

        if (DB::connection()->getDriverName() === 'sqlite') {
            DB::statement("CREATE TRIGGER target_group_versions_previous_not_self_insert BEFORE INSERT ON target_group_file_versions WHEN NEW.previous_version_id = NEW.id BEGIN SELECT RAISE(ABORT, 'previous_version_id cannot equal id'); END");
            DB::statement("CREATE TRIGGER target_group_versions_previous_not_self_update BEFORE UPDATE OF previous_version_id, id ON target_group_file_versions WHEN NEW.previous_version_id = NEW.id BEGIN SELECT RAISE(ABORT, 'previous_version_id cannot equal id'); END");
        } else {
            DB::statement('ALTER TABLE target_group_file_versions ADD CONSTRAINT target_group_versions_previous_not_self CHECK (previous_version_id IS NULL OR previous_version_id <> id)');
        }
    }

    public function down(): void
    {
        if (DB::connection()->getDriverName() === 'sqlite') {
            DB::statement('DROP TRIGGER IF EXISTS target_group_versions_previous_not_self_insert');
            DB::statement('DROP TRIGGER IF EXISTS target_group_versions_previous_not_self_update');
        } else {
            DB::statement('ALTER TABLE target_group_file_versions DROP CONSTRAINT target_group_versions_previous_not_self');
        }

        Schema::table('audit_logs', function (Blueprint $table): void {
            foreach (['import_request_id', 'content_object_id', 'attempt_id', 'lineage_id', 'version_id', 'predecessor_version_id', 'successor_version_id'] as $column) {
                $table->dropForeign([$column]);
            }
        });

        Schema::table('target_group_lineages', function (Blueprint $table): void {
            $table->dropForeign(['active_version_id']);
        });

        Schema::table('target_group_files', function (Blueprint $table): void {
            $table->dropUnique('target_group_files_job_content_unique');
            $table->dropForeign(['content_object_id']);
        });

        Schema::table('target_group_jobs', function (Blueprint $table): void {
            $table->dropUnique('target_group_jobs_import_request_unique');
            $table->dropForeign(['import_request_id']);
            $table->dropForeign(['retry_of_job_id']);
        });

        Schema::table('import_requests', function (Blueprint $table): void {
            $table->dropForeign(['canonical_job_id']);
            $table->dropForeign(['created_by_user_id']);
        });
    }
};
