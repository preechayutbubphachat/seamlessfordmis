<?php

namespace App\Http\Requests;

use App\Services\Export\ExportService;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

final class PreviewExportRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'target_group_job_id' => ['nullable', 'integer', 'exists:target_group_jobs,id', 'required_without:result_generation_job_id'],
            'result_generation_job_id' => ['nullable', 'integer', 'exists:result_generation_jobs,id', 'required_without:target_group_job_id'],
            'categories' => ['nullable', 'array'],
            'categories.*' => ['string', Rule::in(ExportService::RESULT_CATEGORIES)],
        ];
    }

    public function filters(): array
    {
        return [
            'target_group_job_id' => $this->input('target_group_job_id'),
            'result_generation_job_id' => $this->input('result_generation_job_id'),
            'categories' => $this->input('categories', []),
        ];
    }
}
