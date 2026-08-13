<?php

use App\Http\Controllers\Auth\LoginController;
use App\Http\Controllers\ExportController;
use App\Http\Controllers\SourceImportController;
use App\Http\Controllers\TargetGroupController;
use App\Http\Controllers\TargetGroupImportController;
use App\Http\Controllers\TargetGroupResultsController;
use App\Http\Controllers\TargetGroupReviewController;
use Illuminate\Support\Facades\Route;

Route::middleware('guest')->group(function (): void {
    Route::get('/login', [LoginController::class, 'create'])->name('login');
    Route::post('/login', [LoginController::class, 'store'])->name('login.store');
});

Route::post('/logout', [LoginController::class, 'destroy'])
    ->middleware('auth')
    ->name('logout');

Route::get('/', function () {
    return redirect('/dashboard');
});

$placeholderPages = [
    '/dashboard' => [
        'name' => 'admin.dashboard',
        'title' => 'Dashboard',
        'workflow' => 'Operational overview placeholder for future admin-ready status summaries.',
    ],
    '/target-groups' => [
        'name' => 'target-groups.index',
        'title' => 'Target Groups',
        'workflow' => 'Future list of staged target groups after safe import workflows exist.',
    ],
    '/settings/disease-services' => [
        'name' => 'settings.disease-services',
        'title' => 'Disease Services',
        'workflow' => 'Future disease and service catalog management placeholder.',
    ],
    '/audit-logs' => [
        'name' => 'audit-logs.index',
        'title' => 'Audit Logs',
        'workflow' => 'Future audit log review placeholder for important system actions.',
    ],
];

foreach ($placeholderPages as $uri => $page) {
    $permission = match ($uri) {
        '/dashboard' => 'dashboard.view',
        '/settings/disease-services' => 'settings.disease.service.view',
        '/audit-logs' => 'audit.log.view',
        default => 'targetgroup.view',
    };

    Route::get($uri, fn () => view('admin.placeholder', ['page' => $page]))
        ->middleware(['auth', 'permission:'.$permission])
        ->name($page['name']);
}

Route::get('/imports/source-files', [SourceImportController::class, 'index'])
    ->middleware(['auth', 'permission:import.source.view'])
    ->name('imports.source-files');
Route::get('/imports/source-files/preview', [SourceImportController::class, 'previewForm'])
    ->middleware(['auth', 'permission:import.source.preview'])
    ->name('imports.source-files.preview');
Route::post('/imports/source-files/preview', [SourceImportController::class, 'preview'])
    ->middleware(['auth', 'permission:import.source.preview'])
    ->name('imports.source-files.preview.store');
Route::post('/imports/source-files/commit-preview', [SourceImportController::class, 'commitPreview'])
    ->middleware(['auth', 'permission:import.source.commit'])
    ->name('imports.source-files.preview.commit');
Route::post('/imports/source-files', [SourceImportController::class, 'store'])
    ->middleware(['auth', 'permission:import.source.commit'])
    ->name('imports.source-files.store');
Route::get('/imports/source-files/{job}', [SourceImportController::class, 'show'])
    ->whereNumber('job')
    ->middleware(['auth', 'permission:import.source.view'])
    ->name('imports.source-files.show');

Route::get('/imports/target-groups', [TargetGroupImportController::class, 'index'])
    ->middleware(['auth', 'permission:import.targetgroup.view'])
    ->name('imports.target-groups');
Route::get('/imports/target-groups/preview', [TargetGroupImportController::class, 'previewForm'])
    ->middleware(['auth', 'permission:import.targetgroup.preview'])
    ->name('imports.target-groups.preview');
Route::post('/imports/target-groups/preview', [TargetGroupImportController::class, 'preview'])
    ->middleware(['auth', 'permission:import.targetgroup.preview'])
    ->name('imports.target-groups.preview.store');
Route::post('/imports/target-groups/commit-preview', [TargetGroupImportController::class, 'commitPreview'])
    ->middleware(['auth', 'permission:import.targetgroup.commit'])
    ->name('imports.target-groups.preview.commit');
Route::post('/imports/target-groups', [TargetGroupImportController::class, 'store'])
    ->middleware(['auth', 'permission:import.targetgroup.commit'])
    ->name('imports.target-groups.store');
Route::get('/imports/target-groups/{job}', [TargetGroupImportController::class, 'show'])
    ->whereNumber('job')
    ->middleware(['auth', 'permission:import.targetgroup.view'])
    ->name('imports.target-groups.show');

Route::get('/exports', [ExportController::class, 'index'])
    ->middleware(['auth', 'permission:export.view'])
    ->name('exports.index');
Route::get('/exports/preview', [ExportController::class, 'previewForm'])
    ->middleware(['auth', 'permission:export.preview'])
    ->name('exports.preview');
Route::post('/exports/preview', [ExportController::class, 'preview'])
    ->middleware(['auth', 'permission:export.preview'])
    ->name('exports.preview.store');
Route::post('/exports/generate', [ExportController::class, 'generate'])
    ->middleware(['auth', 'permission:export.generate'])
    ->name('exports.generate');
Route::get('/exports/{exportJob}/download', [ExportController::class, 'download'])
    ->whereNumber('exportJob')
    ->middleware(['auth', 'permission:export.download'])
    ->name('exports.download');
Route::post('/exports', [ExportController::class, 'store'])
    ->middleware(['auth', 'permission:export.generate'])
    ->name('exports.store');

Route::get('/target-groups/{id}', [TargetGroupController::class, 'show'])
    ->whereNumber('id')
    ->middleware(['auth', 'permission:targetgroup.view'])
    ->name('target-groups.show');

Route::post('/target-groups/{id}/generate-results', [TargetGroupController::class, 'generateResults'])
    ->whereNumber('id')
    ->middleware(['auth', 'permission:targetgroup.result.generate'])
    ->name('target-groups.generate-results');

Route::get('/target-groups/{id}/results', [TargetGroupResultsController::class, 'index'])
    ->whereNumber('id')
    ->middleware(['auth', 'permission:targetgroup.result.view'])
    ->name('target-groups.results');

Route::middleware(['auth', 'permission:import.targetgroup.review.view'])->group(function (): void {
    Route::get('/target-groups/review', [TargetGroupReviewController::class, 'index'])
        ->name('target-groups.review');
    Route::get('/target-groups/review/{id}', [TargetGroupReviewController::class, 'show'])
        ->whereNumber('id')
        ->name('target-groups.review.show');
});

Route::post('/target-groups/review/{id}/approve', [TargetGroupReviewController::class, 'approve'])
    ->whereNumber('id')
    ->middleware(['auth', 'permission:import.targetgroup.review.approve'])
    ->name('target-groups.review.approve');

Route::post('/target-groups/review/{id}/reject', [TargetGroupReviewController::class, 'reject'])
    ->whereNumber('id')
    ->middleware(['auth', 'permission:import.targetgroup.review.reject'])
    ->name('target-groups.review.reject');
