<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Validator;
use ZipArchive;

final class PreviewCsvImportRequest extends FormRequest
{
    private const ALLOWED_CSV_MIME_TYPES = [
        'text/csv',
        'text/plain',
        'text/x-csv',
        'application/csv',
    ];

    private const XLSX_MIME_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

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

                $extension = strtolower($file->getClientOriginalExtension());
                $mimeType = $file->getMimeType();

                if ($extension === 'csv') {
                    if ($mimeType !== null && ! in_array($mimeType, self::ALLOWED_CSV_MIME_TYPES, true)) {
                        $validator->errors()->add('file', 'Uploaded file must be detectable as CSV text.');
                    }

                    return;
                }

                if ($extension !== 'xlsx' || $mimeType !== self::XLSX_MIME_TYPE) {
                    $validator->errors()->add('file', 'Only CSV or bounded XLSX preview uploads are allowed.');

                    return;
                }

                $zip = new ZipArchive;
                $realPath = (string) $file->getRealPath();
                if (! class_exists(ZipArchive::class) || $realPath === '' || ! is_file($realPath) || $zip->open($realPath) !== true) {
                    $validator->errors()->add('file', 'Uploaded XLSX must be a valid ZIP package.');

                    return;
                }
                $zip->close();
            },
        ];
    }
}
