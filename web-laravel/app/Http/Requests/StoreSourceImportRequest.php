<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rules\File;

final class StoreSourceImportRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'files' => ['required', 'array', 'min:1'],
            'files.*' => [
                'required',
                File::types(['csv', 'txt'])
                    ->max(10 * 1024) // 10MB
            ],
        ];
    }

    public function messages(): array
    {
        return [
            'files.required' => 'At least one CSV file must be uploaded.',
            'files.array' => 'Files must be an array.',
            'files.min' => 'At least one CSV file must be uploaded.',
            'files.*.required' => 'Each file is required.',
            'files.*.file' => 'Each upload must be a file.',
            'files.*.mimes' => 'Only CSV files are allowed.',
            'files.*.max' => 'File size must not exceed 10MB.',
        ];
    }
}