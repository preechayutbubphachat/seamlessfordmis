<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('import_requests', function (Blueprint $table): void {
            $table->uuid('import_request_id')->primary();
            $table->string('operation', 64);
            $table->string('lifecycle_state', 32)->index();
            $table->string('context_fingerprint', 64)->index();
            $table->unsignedBigInteger('canonical_job_id')->nullable()->index();
            $table->uuid('correlation_id')->index();
            $table->unsignedBigInteger('created_by_user_id')->nullable()->index();
            $table->timestamp('created_at')->useCurrent();
            $table->timestamp('completed_at')->nullable();
            $table->string('failure_code', 64)->nullable()->index();
            $table->string('reconciliation_state', 32)->nullable()->index();
            $table->string('reconciliation_reference', 128)->nullable()->index();

            $table->unique(['operation', 'import_request_id'], 'import_requests_operation_request_unique');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('import_requests');
    }
};
