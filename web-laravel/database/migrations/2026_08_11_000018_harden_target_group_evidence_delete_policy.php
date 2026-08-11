<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('target_group_files', function (Blueprint $table): void {
            $table->dropForeign(['target_group_job_id']);
            $table->foreign('target_group_job_id')->references('id')->on('target_group_jobs')->restrictOnDelete();
        });

        Schema::table('target_group_rows', function (Blueprint $table): void {
            $table->dropForeign(['target_group_job_id']);
            $table->dropForeign(['target_group_file_id']);
            $table->foreign('target_group_job_id')->references('id')->on('target_group_jobs')->restrictOnDelete();
            $table->foreign('target_group_file_id')->references('id')->on('target_group_files')->restrictOnDelete();
        });

        Schema::table('target_group_history_rows', function (Blueprint $table): void {
            $table->dropForeign(['target_group_job_id']);
            $table->foreign('target_group_job_id')->references('id')->on('target_group_jobs')->restrictOnDelete();
        });
    }

    public function down(): void
    {
        Schema::table('target_group_history_rows', function (Blueprint $table): void {
            $table->dropForeign(['target_group_job_id']);
            $table->foreign('target_group_job_id')->references('id')->on('target_group_jobs')->cascadeOnDelete();
        });

        Schema::table('target_group_rows', function (Blueprint $table): void {
            $table->dropForeign(['target_group_job_id']);
            $table->dropForeign(['target_group_file_id']);
            $table->foreign('target_group_job_id')->references('id')->on('target_group_jobs')->cascadeOnDelete();
            $table->foreign('target_group_file_id')->references('id')->on('target_group_files')->cascadeOnDelete();
        });

        Schema::table('target_group_files', function (Blueprint $table): void {
            $table->dropForeign(['target_group_job_id']);
            $table->foreign('target_group_job_id')->references('id')->on('target_group_jobs')->cascadeOnDelete();
        });
    }
};
