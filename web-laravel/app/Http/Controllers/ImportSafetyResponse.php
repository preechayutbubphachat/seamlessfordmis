<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;

trait ImportSafetyResponse
{
    protected function importNotEnabled(): JsonResponse
    {
        return response()->json([
            'message' => 'Import execution is not enabled in W4.',
            'file_stored' => false,
            'patient_data_imported' => false,
            'safety_note' => 'No file was stored. No patient data was imported.',
        ], 501);
    }
}
