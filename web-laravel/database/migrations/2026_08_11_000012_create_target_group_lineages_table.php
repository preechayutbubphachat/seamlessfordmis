<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('target_group_lineages', function (Blueprint $table): void {
            $table->uuid('lineage_id')->primary();
            $table->unsignedInteger('next_version_number')->default(1);
            $table->unsignedBigInteger('active_version_id')->nullable()->index();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('target_group_lineages');
    }
};
