<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('target_group_job_attempts', function (Blueprint $table): void {
            $table->uuid('attempt_id')->primary();
            $table->foreignId('job_id')->constrained('target_group_jobs')->restrictOnDelete();
            $table->unsignedInteger('attempt_number');
            $table->string('state', 32)->index();
            $table->string('worker_token', 128)->nullable()->index();
            $table->timestamp('lease_acquired_at')->nullable();
            $table->timestamp('lease_expires_at')->nullable();
            $table->timestamp('started_at')->nullable();
            $table->timestamp('finished_at')->nullable();
            $table->timestamp('last_heartbeat_at')->nullable();
            $table->string('failure_code', 64)->nullable()->index();
            $table->string('last_error_code', 64)->nullable()->index();
            $table->boolean('retryable')->nullable();
            $table->string('reconciliation_state', 32)->nullable()->index();
            $table->string('reconciliation_reference', 128)->nullable()->index();
            $table->uuid('correlation_id')->index();
            $table->timestamp('created_at')->useCurrent();

            $table->unique(['job_id', 'attempt_number'], 'target_group_attempts_job_number_unique');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('target_group_job_attempts');
    }
};
