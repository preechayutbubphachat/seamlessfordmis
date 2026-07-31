<?php

namespace App\Http\Requests;

use App\Services\Export\ExportService;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

final class GenerateExportRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'confirmed' => ['required', 'accepted'],
            'target_group_job_id' => ['required', 'integer', 'exists:target_group_jobs,id'],
            'result_generation_job_id' => [
                'required',
                'integer',
                Rule::exists('result_generation_jobs', 'id')->where(
                    fn ($query) => $query->where('target_group_job_id', $this->integer('target_group_job_id'))
                ),
            ],
            'categories' => ['sometimes', 'array', 'min:1'],
            'categories.*' => ['required', 'string', 'distinct', Rule::in(ExportService::RESULT_CATEGORIES)],
            'requested_by_user_id' => ['prohibited'],
            'user_id' => ['prohibited'],
            'role' => ['prohibited'],
            'permission' => ['prohibited'],
            'filename' => ['prohibited'],
            'stored_path' => ['prohibited'],
            'output_path' => ['prohibited'],
            'columns' => ['prohibited'],
            'download' => ['prohibited'],
            'visibility' => ['prohibited'],
            'filters' => ['prohibited'],
            'sql' => ['prohibited'],
            'sort' => ['prohibited'],
            'policy_version' => ['prohibited'],
        ];
    }

    public function exportFilters(): array
    {
        return [
            'target_group_job_id' => $this->integer('target_group_job_id'),
            'result_generation_job_id' => $this->integer('result_generation_job_id'),
            'categories' => array_values($this->validated('categories', [])),
        ];
    }
}
