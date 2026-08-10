<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('target_group_rows', function (Blueprint $table): void {
            $table->string('review_status')->default('PENDING_VALIDATION')->index();
            $table->string('review_reason_code')->nullable()->index();
            $table->string('review_outcome')->nullable();
            $table->foreignId('reviewed_by')->nullable()->constrained('users')->nullOnDelete();
            $table->timestamp('reviewed_at')->nullable();
            $table->string('matching_key_type')->nullable();
            $table->string('matching_key_version')->nullable();
            $table->string('normalization_version')->nullable();
            $table->string('validation_version')->nullable();
            $table->json('conflict_flags')->nullable();
            $table->index(['review_status', 'target_group_job_id']);
        });
    }

    public function down(): void
    {
        Schema::table('target_group_rows', function (Blueprint $table): void {
            $table->dropForeign(['reviewed_by']);
            $table->dropIndex(['review_status', 'target_group_job_id']);
            $table->dropColumn([
                'review_status',
                'review_reason_code',
                'review_outcome',
                'reviewed_by',
                'reviewed_at',
                'matching_key_type',
                'matching_key_version',
                'normalization_version',
                'validation_version',
                'conflict_flags',
            ]);
        });
    }
};
