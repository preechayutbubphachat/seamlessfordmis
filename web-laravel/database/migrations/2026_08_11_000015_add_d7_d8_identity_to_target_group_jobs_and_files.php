<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('target_group_jobs', function (Blueprint $table): void {
            $table->uuid('import_request_id')->nullable()->index();
            $table->foreignId('retry_of_job_id')->nullable()->index();
        });

        Schema::table('target_group_files', function (Blueprint $table): void {
            $table->foreignId('content_object_id')->nullable()->index();
        });
    }

    public function down(): void
    {
        Schema::table('target_group_files', function (Blueprint $table): void {
            $table->dropIndex(['content_object_id']);
            $table->dropColumn('content_object_id');
        });

        Schema::table('target_group_jobs', function (Blueprint $table): void {
            $table->dropIndex(['import_request_id']);
            $table->dropIndex(['retry_of_job_id']);
            $table->dropColumn(['import_request_id', 'retry_of_job_id']);
        });
    }
};
