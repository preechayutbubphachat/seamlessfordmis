<?php

namespace App\Http\Controllers;

use App\Http\Requests\StoreTargetGroupReviewDecisionRequest;
use App\Models\TargetGroupRow;
use App\Services\Review\TargetGroupReviewService;
use Illuminate\Contracts\View\View;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;

final class TargetGroupReviewController extends Controller
{
    public function index(Request $request, TargetGroupReviewService $service): View
    {
        $rows = TargetGroupRow::query()
            ->where('review_status', TargetGroupReviewService::STATE_NEEDS_REVIEW)
            ->orderBy('id')
            ->get()
            ->map(fn (TargetGroupRow $row): TargetGroupRow => $this->present($row, $request));

        return view('target-groups.review', [
            'rows' => $rows,
            'row' => null,
            'foundationReasons' => $service->foundationReasonCodes(),
        ]);
    }

    public function show(Request $request, int $id, TargetGroupReviewService $service): View
    {
        $row = TargetGroupRow::query()->findOrFail($id);

        return view('target-groups.review', [
            'rows' => collect([$this->present($row, $request)]),
            'row' => $this->present($row, $request),
            'foundationReasons' => $service->foundationReasonCodes(),
        ]);
    }

    public function approve(
        StoreTargetGroupReviewDecisionRequest $request,
        int $id,
        TargetGroupReviewService $service,
    ): RedirectResponse {
        $row = TargetGroupRow::query()->findOrFail($id);
        $service->decide($row, TargetGroupReviewService::OUTCOME_APPROVED, $request->validated('review_reason_code'), $this->context($request));

        return redirect()->route('target-groups.review.show', ['id' => $id])->with('status', 'Review approved.');
    }

    public function reject(
        StoreTargetGroupReviewDecisionRequest $request,
        int $id,
        TargetGroupReviewService $service,
    ): RedirectResponse {
        $row = TargetGroupRow::query()->findOrFail($id);
        $service->decide($row, TargetGroupReviewService::OUTCOME_REJECTED, $request->validated('review_reason_code'), $this->context($request));

        return redirect()->route('target-groups.review.show', ['id' => $id])->with('status', 'Review rejected.');
    }

    private function context(Request $request): array
    {
        return [
            'actor_user_id' => $request->user()?->getKey(),
            'ip_address' => $request->ip(),
            'user_agent' => $request->userAgent(),
            'correlation_id' => $request->header('X-Correlation-ID'),
            'operator_note' => $request->validated('note'),
        ];
    }

    private function present(TargetGroupRow $row, Request $request): TargetGroupRow
    {
        $row->setAttribute('masked_cid', $this->mask($row->raw_cid));
        $row->setAttribute('masked_name', $this->mask($row->raw_full_name));
        $row->setAttribute('masked_birth_date', $row->raw_birth_date === null ? '[missing]' : '****-**-**');

        if ($request->user()?->hasPermission('import.targetgroup.identity.view')) {
            $row->setAttribute('authorized_identity', [
                'cid' => $row->raw_cid,
                'name' => $row->raw_full_name,
                'birth_date' => $row->raw_birth_date,
            ]);
        }

        return $row;
    }

    private function mask(?string $value): string
    {
        $value = trim((string) $value);

        if ($value === '') {
            return '[missing]';
        }

        $visibleCharacters = min(4, strlen($value));

        return str_repeat('*', strlen($value) - $visibleCharacters).substr($value, -$visibleCharacters);
    }
}
