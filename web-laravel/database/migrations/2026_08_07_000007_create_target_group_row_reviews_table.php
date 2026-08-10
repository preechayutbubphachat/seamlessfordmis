<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('target_group_row_reviews', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('target_group_job_id')->constrained('target_group_jobs')->restrictOnDelete();
            $table->foreignId('target_group_file_id')->constrained('target_group_files')->restrictOnDelete();
            $table->foreignId('target_group_row_id')->constrained('target_group_rows')->restrictOnDelete();
            $table->foreignId('reviewed_by')->nullable()->constrained('users')->nullOnDelete();
            $table->string('correlation_id', 64)->index();
            $table->string('from_status');
            $table->string('to_status');
            $table->string('review_outcome')->nullable();
            $table->string('review_reason_code')->nullable()->index();
            $table->string('matching_key_type')->nullable();
            $table->string('matching_key_version')->nullable();
            $table->string('normalization_version')->nullable();
            $table->string('validation_version')->nullable();
            $table->json('conflict_flags')->nullable();
            $table->json('evidence_references')->nullable();
            $table->text('operator_note')->nullable();
            $table->timestamp('reviewed_at')->nullable();
            $table->timestamp('created_at')->useCurrent();
            $table->index(['target_group_row_id', 'created_at']);
            $table->index(['target_group_job_id', 'to_status']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('target_group_row_reviews');
    }
};
