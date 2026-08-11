<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('target_group_file_versions', function (Blueprint $table): void {
            $table->id();
            $table->uuid('lineage_id');
            $table->uuid('version_token')->unique('target_group_versions_token_unique');
            $table->unsignedInteger('version_number');
            $table->foreignId('target_group_file_id')->constrained('target_group_files')->restrictOnDelete();
            $table->foreignId('target_group_job_id')->constrained('target_group_jobs')->restrictOnDelete();
            $table->unsignedBigInteger('previous_version_id')->nullable();
            $table->unsignedBigInteger('superseded_by_id')->nullable();
            $table->string('version_status', 32)->index();
            $table->string('correction_reason', 64)->nullable()->index();
            $table->string('supersession_reason', 64)->nullable()->index();
            $table->timestamp('superseded_at')->nullable();
            $table->foreignId('superseded_by_user_id')->nullable()->constrained('users')->nullOnDelete();
            $table->foreignId('confirmed_by_user_id')->nullable()->constrained('users')->nullOnDelete();
            $table->uuid('correlation_id')->index();
            $table->timestamps();

            $table->foreign('lineage_id', 'target_group_versions_lineage_foreign')
                ->references('lineage_id')->on('target_group_lineages')->restrictOnDelete();
            $table->foreign('previous_version_id', 'target_group_versions_previous_foreign')
                ->references('id')->on('target_group_file_versions')->restrictOnDelete();
            $table->foreign('superseded_by_id', 'target_group_versions_successor_foreign')
                ->references('id')->on('target_group_file_versions')->restrictOnDelete();
            $table->unique(['lineage_id', 'version_number'], 'target_group_versions_lineage_number_unique');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('target_group_file_versions');
    }
};
