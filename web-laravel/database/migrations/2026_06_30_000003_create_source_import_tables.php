<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('source_import_jobs', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('created_by_user_id')->nullable()->constrained('users')->nullOnDelete();
            $table->string('job_name');
            $table->string('status')->index();
            $table->unsignedInteger('total_files')->default(0);
            $table->unsignedInteger('total_rows')->default(0);
            $table->unsignedInteger('valid_rows')->default(0);
            $table->unsignedInteger('invalid_rows')->default(0);
            $table->unsignedInteger('review_rows')->default(0);
            $table->text('error_message')->nullable();
            $table->timestamp('started_at')->nullable();
            $table->timestamp('finished_at')->nullable();
            $table->timestamps();
        });

        Schema::create('source_import_files', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('source_import_job_id')->constrained()->cascadeOnDelete();
            $table->string('original_filename');
            $table->string('stored_path');
            $table->string('mime_type')->nullable();
            $table->unsignedBigInteger('size_bytes');
            $table->string('sha256', 64)->index();
            $table->unsignedInteger('sheet_count')->nullable();
            $table->unsignedInteger('row_count')->nullable();
            $table->timestamps();
        });

        Schema::create('source_import_rows', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('source_import_job_id')->constrained()->cascadeOnDelete();
            $table->foreignId('source_file_id')->constrained('source_import_files')->cascadeOnDelete();
            $table->string('sheet_name')->nullable();
            $table->unsignedInteger('row_number');
            $table->json('raw_payload');
            $table->string('raw_cid', 32)->nullable();
            $table->string('normalized_cid', 13)->nullable()->index();
            $table->string('cid_status')->index();
            $table->string('raw_full_name')->nullable();
            $table->string('normalized_full_name')->nullable();
            $table->string('raw_service_text')->nullable();
            $table->string('normalized_service_key')->nullable()->index();
            $table->string('raw_visit_date')->nullable();
            $table->date('normalized_visit_date')->nullable()->index();
            $table->string('validation_status')->index();
            $table->text('review_reason')->nullable();
            $table->timestamps();
            $table->index(['source_import_job_id', 'validation_status']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('source_import_rows');
        Schema::dropIfExists('source_import_files');
        Schema::dropIfExists('source_import_jobs');
    }
};
