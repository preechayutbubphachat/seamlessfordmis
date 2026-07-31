<?php

namespace App\Http\Controllers;

use Illuminate\Contracts\View\View;
use Illuminate\Support\Facades\DB;

final class TargetGroupResultsController extends Controller
{
    public function index(int $id): View
    {
        $results = DB::table('target_group_results')
            ->where('target_group_job_id', $id)
            ->orderBy('id')
            ->get()
            ->map(function (object $result): object {
                $result->evidence_summary_decoded = $this->decodeJson($result->evidence_summary);
                $result->selected_service_keys_decoded = $this->decodeJson($result->selected_service_keys);
                $result->sources = DB::table('target_group_result_sources')
                    ->where('target_group_result_id', $result->id)
                    ->orderBy('id')
                    ->get()
                    ->map(function (object $source): object {
                        $source->source_payload_decoded = $this->decodeJson($source->source_payload);
                        $source->provenance_decoded = $this->decodeJson($source->provenance);

                        return $source;
                    });

                return $result;
            });

        return view('target-groups.results', [
            'targetGroupJobId' => $id,
            'results' => $results,
        ]);
    }

    private function decodeJson(?string $json): array
    {
        if ($json === null || $json === '') {
            return [];
        }

        $decoded = json_decode($json, true);

        return is_array($decoded) ? $decoded : [];
    }
}
