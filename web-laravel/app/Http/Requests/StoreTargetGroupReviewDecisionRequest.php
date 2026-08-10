<?php

namespace App\Http\Requests;

use App\Services\Review\TargetGroupReviewService;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

final class StoreTargetGroupReviewDecisionRequest extends FormRequest
{
    public function authorize(): bool
    {
        return $this->user() !== null;
    }

    public function rules(): array
    {
        return [
            'review_reason_code' => [
                'required',
                'string',
                Rule::in(TargetGroupReviewService::FOUNDATION_REASON_CODES),
            ],
            'note' => ['nullable', 'string', 'max:2000'],
        ];
    }
}
