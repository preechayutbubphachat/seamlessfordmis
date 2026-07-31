<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('result_generation_jobs', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('target_group_job_id')->constrained()->cascadeOnDelete();
            $table->foreignId('created_by_user_id')->nullable()->constrained('users')->nullOnDelete();
            $table->string('status')->index();
            $table->json('selected_service_keys');
            $table->unsignedInteger('normalization_version')->default(1);
            $table->string('source_set_hash', 64)->nullable()->index();
            $table->unsignedInteger('total_persons')->default(0);
            $table->unsignedInteger('completed_persons')->default(0);
            $table->text('error_message')->nullable();
            $table->timestamp('started_at')->nullable();
            $table->timestamp('finished_at')->nullable();
            $table->timestamps();
        });

        Schema::create('target_group_results', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('target_group_job_id')->constrained()->cascadeOnDelete();
            $table->foreignId('result_generation_job_id')->constrained()->cascadeOnDelete();
            $table->string('normalized_cid', 13)->nullable()->index();
            $table->string('person_key')->index();
            $table->string('display_name')->nullable();
            $table->string('result_category')->index();
            $table->boolean('has_screening_db_history')->default(false);
            $table->boolean('has_target_group_file_history')->default(false);
            $table->boolean('has_any_history')->default(false);
            $table->date('latest_history_date')->nullable()->index();
            $table->string('latest_history_source')->nullable();
            $table->json('selected_service_keys');
            $table->json('evidence_summary');
            $table->string('review_status')->index();
            $table->text('review_reason')->nullable();
            $table->timestamps();
        });

        Schema::create('target_group_result_sources', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('target_group_result_id')->constrained()->cascadeOnDelete();
            $table->string('source_type')->index();
            $table->unsignedBigInteger('source_file_id')->nullable()->index();
            $table->string('sheet_name')->nullable();
            $table->unsignedInteger('row_number')->nullable();
            $table->json('source_payload');
            $table->date('evidence_date')->nullable()->index();
            $table->string('normalized_service_key')->nullable()->index();
            $table->json('provenance');
            $table->timestamps();
        });

        Schema::create('export_jobs', function (Blueprint $table): void {
            $table->id();
            $table->string('export_type')->index();
            $table->string('status')->index();
            $table->foreignId('requested_by_user_id')->nullable()->constrained('users')->nullOnDelete();
            $table->json('filters');
            $table->string('stored_path')->nullable();
            $table->unsignedInteger('row_count')->nullable();
            $table->text('error_message')->nullable();
            $table->timestamp('started_at')->nullable();
            $table->timestamp('finished_at')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('export_jobs');
        Schema::dropIfExists('target_group_result_sources');
        Schema::dropIfExists('target_group_results');
        Schema::dropIfExists('result_generation_jobs');
    }
};
