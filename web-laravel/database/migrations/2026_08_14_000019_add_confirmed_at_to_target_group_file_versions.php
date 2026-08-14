<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('target_group_file_versions', function (Blueprint $table): void {
            $table->timestamp('confirmed_at')->nullable()->after('confirmed_by_user_id');
        });
    }

    public function down(): void
    {
        Schema::table('target_group_file_versions', function (Blueprint $table): void {
            $table->dropColumn('confirmed_at');
        });
    }
};
