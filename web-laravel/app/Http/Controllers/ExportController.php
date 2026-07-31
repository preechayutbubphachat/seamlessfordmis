<?php

namespace App\Http\Controllers;

use App\Http\Requests\GenerateExportRequest;
use App\Http\Requests\PreviewExportRequest;
use App\Models\ExportJob;
use App\Services\Export\DownloadPrivateCsvArtifact;
use App\Services\Export\ExportDisclosurePolicy;
use App\Services\Export\ExportService;
use DomainException;
use Illuminate\Contracts\View\View;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;
use RuntimeException;
use Symfony\Component\HttpFoundation\Response;

final class ExportController extends Controller
{
    public function index(): View
    {
        return view('exports.index', [
            'exportJobs' => DB::table('export_jobs')->orderByDesc('id')->get(),
        ]);
    }

    public function previewForm(): View
    {
        return view('exports.preview', [
            'preview' => null,
            'categories' => ExportService::RESULT_CATEGORIES,
        ]);
    }

    public function preview(PreviewExportRequest $request, ExportService $exportService): View
    {
        try {
            $preview = $exportService->buildExportPreview($request->filters());
        } catch (InvalidArgumentException $exception) {
            return view('exports.preview', [
                'preview' => null,
                'categories' => ExportService::RESULT_CATEGORIES,
                'eligibilityError' => $exception->getMessage(),
            ]);
        }

        return view('exports.preview', [
            'preview' => $preview,
            'categories' => ExportService::RESULT_CATEGORIES,
        ]);
    }

    public function store(Request $request, ExportService $exportService): JsonResponse
    {
        $job = $exportService->createBlockedExportJob(
            (string) $request->input('export_type', 'result_review'),
            ['source' => 'stored_target_group_results_only']
        );

        return response()->json([
            'message' => 'Export generation is not enabled yet.',
            'file_created' => false,
            'export_job_id' => $job['id'],
            'status' => $job['status'],
        ], 501);
    }

    public function generate(
        GenerateExportRequest $request,
        ExportService $exportService,
    ): RedirectResponse {
        $filters = $request->exportFilters();
        $filters['requested_by_user_id'] = (int) $request->user()->id;
        $filters['policy_version'] = ExportDisclosurePolicy::VERSION;

        try {
            $exportService->assertExportEligible($filters);
            $job = $exportService->createAndGenerateCsvExport($filters);
        } catch (InvalidArgumentException|DomainException) {
            return redirect()
                ->route('exports.index')
                ->withErrors(['export' => 'Export is not eligible for the selected persisted result context.']);
        } catch (RuntimeException) {
            return redirect()
                ->route('exports.index')
                ->withErrors(['export' => 'Private export generation failed safely.']);
        }

        return redirect()
            ->route('exports.index')
            ->with('status', "Export job #{$job->id} completed with {$job->row_count} stored result rows.");
    }

    public function download(
        Request $request,
        ExportJob $exportJob,
        DownloadPrivateCsvArtifact $downloadArtifact,
    ): Response {
        return $downloadArtifact->forOwner($exportJob, $request);
    }
}
