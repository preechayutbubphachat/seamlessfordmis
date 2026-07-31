<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Validator;

final class PreviewCsvImportRequest extends FormRequest
{
    private const ALLOWED_MIME_TYPES = [
        'text/csv',
        'text/plain',
        'text/x-csv',
        'application/csv',
    ];

    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'file' => ['required', 'file', 'max:1024'],
        ];
    }

    public function after(): array
    {
        return [
            function (Validator $validator): void {
                $file = $this->file('file');

                if ($file === null || ! $file->isValid()) {
                    return;
                }

                if (strtolower($file->getClientOriginalExtension()) !== 'csv') {
                    $validator->errors()->add('file', 'Only CSV preview uploads are allowed.');
                }

                $mimeType = $file->getMimeType();

                if ($mimeType !== null && ! in_array($mimeType, self::ALLOWED_MIME_TYPES, true)) {
                    $validator->errors()->add('file', 'Uploaded file must be detectable as CSV text.');
                }
            },
        ];
    }
}
