<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('import_content_objects', function (Blueprint $table): void {
            $table->id();
            $table->string('sha256', 64)->unique('import_content_objects_sha256_unique');
            $table->unsignedBigInteger('byte_size');
            $table->timestamp('registered_at')->useCurrent();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('import_content_objects');
    }
};
