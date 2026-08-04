<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::table('source_import_files', function (Blueprint $table) {
            // Database-enforced duplicate prevention for source import files
            // sha256 is already indexed; add unique constraint for concurrency-safe deduplication
            $table->unique('sha256', 'source_import_files_sha256_unique');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::table('source_import_files', function (Blueprint $table) {
            $table->dropUnique('source_import_files_sha256_unique');
        });
    }
};