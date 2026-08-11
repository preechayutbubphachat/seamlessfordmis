<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('audit_logs', function (Blueprint $table): void {
            $table->uuid('import_request_id')->nullable()->index();
            $table->foreignId('content_object_id')->nullable()->index();
            $table->uuid('attempt_id')->nullable()->index();
            $table->uuid('lineage_id')->nullable()->index();
            $table->foreignId('version_id')->nullable()->index();
            $table->uuid('version_token')->nullable()->index();
            $table->unsignedInteger('version_number')->nullable();
            $table->foreignId('predecessor_version_id')->nullable()->index();
            $table->foreignId('successor_version_id')->nullable()->index();
            $table->string('conflict_code', 64)->nullable()->index();
            $table->string('reconciliation_outcome', 64)->nullable()->index();
        });
    }

    public function down(): void
    {
        Schema::table('audit_logs', function (Blueprint $table): void {
            foreach ([
                'import_request_id',
                'content_object_id',
                'attempt_id',
                'lineage_id',
                'version_id',
                'version_token',
                'predecessor_version_id',
                'successor_version_id',
                'conflict_code',
                'reconciliation_outcome',
            ] as $column) {
                $table->dropIndex([$column]);
            }

            $table->dropColumn([
                'import_request_id',
                'content_object_id',
                'attempt_id',
                'lineage_id',
                'version_id',
                'version_token',
                'version_number',
                'predecessor_version_id',
                'successor_version_id',
                'conflict_code',
                'reconciliation_outcome',
            ]);
        });
    }
};
