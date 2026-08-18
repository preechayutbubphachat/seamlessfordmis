<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('source_import_rows', function (Blueprint $table): void {
            $table->string('matching_key_version', 32)->nullable();
            $table->string('normalization_version', 64)->nullable();
            $table->string('validation_version', 64)->nullable();
            $table->string('scope_context_id', 191)->nullable();

            $table->index(
                ['scope_context_id', 'normalized_cid', 'normalized_service_key'],
                'source_import_rows_history_scope_cid_service_index',
            );
            $table->index(
                ['matching_key_version', 'normalization_version', 'validation_version'],
                'source_import_rows_history_key_versions_index',
            );
        });

        Schema::table('target_group_history_rows', function (Blueprint $table): void {
            $table->string('normalized_cid', 13)->nullable();
            $table->string('matching_key_version', 32)->nullable();
            $table->string('normalization_version', 64)->nullable();
            $table->string('validation_version', 64)->nullable();
            $table->string('scope_context_id', 191)->nullable();
            $table->foreignId('target_group_file_version_id')
                ->nullable()
                ->constrained('target_group_file_versions')
                ->restrictOnDelete();

            $table->index(
                ['scope_context_id', 'normalized_cid', 'normalized_service_key'],
                'target_group_history_rows_history_scope_cid_service_index',
            );
            $table->index(
                ['target_group_file_version_id', 'normalized_cid'],
                'target_group_history_rows_version_cid_index',
            );
            $table->index(
                ['matching_key_version', 'normalization_version', 'validation_version'],
                'target_group_history_rows_history_key_versions_index',
            );
        });
    }

    public function down(): void
    {
        Schema::table('target_group_history_rows', function (Blueprint $table): void {
            $table->dropForeign(['target_group_file_version_id']);
            $table->dropIndex('target_group_history_rows_history_scope_cid_service_index');
            $table->dropIndex('target_group_history_rows_version_cid_index');
            $table->dropIndex('target_group_history_rows_history_key_versions_index');
            $table->dropColumn([
                'normalized_cid',
                'matching_key_version',
                'normalization_version',
                'validation_version',
                'scope_context_id',
                'target_group_file_version_id',
            ]);
        });

        Schema::table('source_import_rows', function (Blueprint $table): void {
            $table->dropIndex('source_import_rows_history_scope_cid_service_index');
            $table->dropIndex('source_import_rows_history_key_versions_index');
            $table->dropColumn([
                'matching_key_version',
                'normalization_version',
                'validation_version',
                'scope_context_id',
            ]);
        });
    }
};
