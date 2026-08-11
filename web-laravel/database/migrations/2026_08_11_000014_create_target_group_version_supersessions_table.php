<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('target_group_version_supersessions', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('predecessor_version_id')->constrained('target_group_file_versions')->restrictOnDelete();
            $table->foreignId('successor_version_id')->constrained('target_group_file_versions')->restrictOnDelete();
            $table->foreignId('committed_by_user_id')->nullable()->constrained('users')->nullOnDelete();
            $table->uuid('correlation_id')->index();
            $table->string('supersession_reason', 64);
            $table->timestamp('committed_at')->useCurrent();
            $table->timestamps();

            $table->unique('predecessor_version_id', 'target_group_supersessions_predecessor_unique');
            $table->unique('successor_version_id', 'target_group_supersessions_successor_unique');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('target_group_version_supersessions');
    }
};
