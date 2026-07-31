<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

final class CommitPreviewImportRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'confirmed' => ['accepted'],
            'import_type' => ['required', Rule::in(['source', 'target_group'])],
            'preview_token' => ['required', 'string', 'size:64'],
        ];
    }
}
