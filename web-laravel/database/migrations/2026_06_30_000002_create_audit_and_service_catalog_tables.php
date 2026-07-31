<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('audit_logs', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('actor_user_id')->nullable()->constrained('users')->nullOnDelete();
            $table->string('action')->index();
            $table->string('entity_type')->index();
            $table->unsignedBigInteger('entity_id')->nullable()->index();
            $table->string('ip_address', 45)->nullable();
            $table->text('user_agent')->nullable();
            $table->json('before_payload')->nullable();
            $table->json('after_payload')->nullable();
            $table->timestamp('created_at')->useCurrent();
        });

        Schema::create('disease_services', function (Blueprint $table): void {
            $table->id();
            $table->string('service_key')->unique();
            $table->string('display_name');
            $table->text('description')->nullable();
            $table->boolean('is_active')->default(true)->index();
            $table->timestamps();
        });

        Schema::create('disease_service_aliases', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('disease_service_id')->constrained()->cascadeOnDelete();
            $table->enum('alias_type', ['code', 'text', 'keyword']);
            $table->string('alias_value');
            $table->timestamps();
            $table->unique(['alias_type', 'alias_value']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('disease_service_aliases');
        Schema::dropIfExists('disease_services');
        Schema::dropIfExists('audit_logs');
    }
};
