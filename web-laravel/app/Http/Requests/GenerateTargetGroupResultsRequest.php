<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

final class GenerateTargetGroupResultsRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'confirmed' => ['accepted'],
            'selected_service_keys' => ['required', 'array', 'min:1'],
            'selected_service_keys.*' => ['required', 'string'],
        ];
    }
}
