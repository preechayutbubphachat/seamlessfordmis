<?php

namespace App\Http\Controllers;

use App\Http\Requests\GenerateTargetGroupResultsRequest;
use App\Services\Audit\AuditLogger;
use App\Services\Result\ResultGenerationService;
use Illuminate\Contracts\View\View;
use Illuminate\Http\RedirectResponse;
use Illuminate\Support\Facades\DB;

final class TargetGroupController extends Controller
{
    public function show(int $id): View
    {
        $targetGroupJob = DB::table('target_group_jobs')->where('id', $id)->first();
        $rowCount = DB::table('target_group_rows')->where('target_group_job_id', $id)->count();
        $services = DB::table('disease_services')
            ->where('is_active', true)
            ->orderBy('service_key')
            ->get(['service_key', 'display_name']);

        return view('target-groups.show', [
            'targetGroupJobId' => $id,
            'targetGroupJob' => $targetGroupJob,
            'rowCount' => $rowCount,
            'services' => $services,
        ]);
    }

    public function generateResults(
        int $id,
        GenerateTargetGroupResultsRequest $request,
        ResultGenerationService $resultGenerationService,
        AuditLogger $auditLogger,
    ): RedirectResponse {
        $targetGroupJob = DB::table('target_group_jobs')->where('id', $id)->first();

        if ($targetGroupJob === null) {
            abort(404);
        }

        $rowCount = DB::table('target_group_rows')->where('target_group_job_id', $id)->count();

        if ($rowCount === 0) {
            return back()->withErrors(['target_group_job' => 'Cannot generate results from a target group job with no staged rows.']);
        }

        $selectedServiceKeys = array_values(array_filter(
            $request->input('selected_service_keys', []),
            fn (string $serviceKey): bool => trim($serviceKey) !== ''
        ));

        $summary = DB::transaction(function () use ($id, $selectedServiceKeys, $request, $resultGenerationService, $auditLogger): array {
            $drafts = $resultGenerationService->buildDraftsFromTargetGroupJob($id, $selectedServiceKeys);

            if ($drafts === []) {
                return [
                    'error' => 'Cannot generate results from a target group job with no staged rows.',
                ];
            }

            $summary = $resultGenerationService->persistResultDraftsForJob($id, $drafts, [
                'selected_service_keys' => $selectedServiceKeys,
            ]);

            $auditLogger->log('result_generation_committed', 'target_group_job', $id, [
                'ip_address' => $request->ip(),
                'user_agent' => $request->userAgent(),
                'after_payload' => [
                    'selected_service_keys' => $selectedServiceKeys,
                    'result_generation_job_id' => $summary['result_generation_job_id'],
                    'persisted_results' => $summary['persisted_results'],
                    'export_created' => false,
                ],
            ]);

            return $summary;
        });

        if (isset($summary['error'])) {
            return back()->withErrors(['target_group_job' => $summary['error']]);
        }

        return redirect()
            ->route('target-groups.results', ['id' => $id])
            ->with('status', 'Result drafts generated from staged data.');
    }
}
