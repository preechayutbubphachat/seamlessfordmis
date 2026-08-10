<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('audit_logs', function (Blueprint $table): void {
            $table->string('correlation_id', 64)->nullable()->index();
            $table->foreignId('target_group_job_id')->nullable()->constrained('target_group_jobs')->restrictOnDelete();
            $table->foreignId('target_group_file_id')->nullable()->constrained('target_group_files')->restrictOnDelete();
            $table->foreignId('target_group_row_id')->nullable()->constrained('target_group_rows')->restrictOnDelete();
            $table->string('matching_key_type')->nullable();
            $table->string('matching_key_version')->nullable();
            $table->string('review_reason_code')->nullable()->index();
            $table->string('review_outcome')->nullable();
            $table->json('conflict_flags')->nullable();
            $table->foreignId('reviewed_by')->nullable()->constrained('users')->nullOnDelete();
            $table->timestamp('reviewed_at')->nullable();
            $table->index(['target_group_row_id', 'created_at']);
        });
    }

    public function down(): void
    {
        Schema::table('audit_logs', function (Blueprint $table): void {
            $table->dropForeign(['target_group_job_id']);
            $table->dropForeign(['target_group_file_id']);
            $table->dropForeign(['target_group_row_id']);
            $table->dropForeign(['reviewed_by']);
            $table->dropIndex(['target_group_row_id', 'created_at']);
            $table->dropColumn([
                'correlation_id',
                'target_group_job_id',
                'target_group_file_id',
                'target_group_row_id',
                'matching_key_type',
                'matching_key_version',
                'review_reason_code',
                'review_outcome',
                'conflict_flags',
                'reviewed_by',
                'reviewed_at',
            ]);
        });
    }
};
