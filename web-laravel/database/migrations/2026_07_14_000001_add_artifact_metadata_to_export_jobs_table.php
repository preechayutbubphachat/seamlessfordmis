<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('export_jobs', function (Blueprint $table): void {
            $table->string('generated_filename')->nullable();
            $table->string('mime_type', 100)->nullable();
            $table->unsignedBigInteger('byte_count')->nullable();
            $table->char('sha256', 64)->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('export_jobs', function (Blueprint $table): void {
            $table->dropColumn([
                'generated_filename',
                'mime_type',
                'byte_count',
                'sha256',
            ]);
        });
    }
};
