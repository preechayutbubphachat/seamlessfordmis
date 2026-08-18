<?php

namespace Tests\Feature;

use App\Models\Permission;
use App\Models\Role;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class SourceImportErrorExportTest extends TestCase
{
    use RefreshDatabase;

    public function test_authorized_source_view_user_downloads_only_current_job_non_valid_rows_in_exact_contract(): void
    {
        $user = $this->createAuthorizedUser('source-errors-authorized@example.invalid');
        $jobId = $this->createSourceJob();
        $otherJobId = $this->createSourceJob();
        $validRowId = $this->createSourceRow($jobId, 'valid', 'VALID_PATIENT_MARKER');
        $failedRowId = $this->createSourceRow($jobId, 'invalid_identifier', 'FAILED_PATIENT_MARKER');
        $missingRowId = $this->createSourceRow($jobId, 'missing_identifier', 'MISSING_PATIENT_MARKER');
        $formulaRowId = $this->createSourceRow($jobId, '=2+2', 'FORMULA_PATIENT_MARKER');
        $this->createSourceRow($otherJobId, 'invalid_identifier', 'OTHER_JOB_PATIENT_MARKER');

        $sourceRowsBefore = DB::table('source_import_rows')->count();
        $sourceJobsBefore = DB::table('source_import_jobs')->count();
        $filesBefore = DB::table('source_import_files')->count();

        $response = $this->actingAs($user)->get("/imports/source-files/{$jobId}/errors");

        $response->assertOk()->assertDownload("source-import-errors-job-{$jobId}.csv");
        $body = $response->streamedContent();
        $csv = substr($body, 3);
        $lines = array_values(array_filter(explode("\r\n", $csv), static fn (string $line): bool => $line !== ''));
        $records = array_map('str_getcsv', $lines);
        $this->assertSame([
            'source_import_job_id',
            'source_import_row_id',
            'validation_status',
            'error_code',
            'safe_message',
        ], $records[0]);
        $rows = array_slice($records, 1);
        $this->assertCount(3, $rows);
        foreach ($rows as $row) {
            $this->assertCount(5, $row);
            $this->assertSame((string) $jobId, $row[0]);
            $this->assertSame('SOURCE_ROW_VALIDATION_FAILED', $row[3]);
            $this->assertSame('Row failed source import validation.', $row[4]);
        }
        $this->assertSame((string) $failedRowId, $rows[0][1]);
        $this->assertSame('invalid_identifier', $rows[0][2]);
        $this->assertSame((string) $missingRowId, $rows[1][1]);
        $this->assertSame('missing_identifier', $rows[1][2]);
        $this->assertSame((string) $formulaRowId, $rows[2][1]);
        $this->assertSame("'=2+2", $rows[2][2]);
        $this->assertNotSame((string) $validRowId, $rows[0][1]);
        $this->assertStringNotContainsString('OTHER_JOB_PATIENT_MARKER', $body);
        $this->assertStringNotContainsString('VALID_PATIENT_MARKER', $body);
        $this->assertStringNotContainsString('FAILED_PATIENT_MARKER', $body);
        $this->assertStringNotContainsString('MISSING_PATIENT_MARKER', $body);
        $this->assertStringNotContainsString('FORMULA_PATIENT_MARKER', $body);
        $this->assertStringNotContainsString('raw_payload', $body);
        $this->assertStringNotContainsString('review_reason', $body);

        $audit = DB::table('audit_logs')->where('action', 'source_import_error_exported')->sole();
        $payload = json_decode($audit->after_payload, true, flags: JSON_THROW_ON_ERROR);
        $this->assertSame($user->id, $audit->actor_user_id);
        $this->assertSame('source_import_job', $audit->entity_type);
        $this->assertSame($jobId, $audit->entity_id);
        $this->assertSame([
            'source_import_job_id' => $jobId,
            'exported_error_count' => 3,
            'format' => 'csv',
        ], $payload);
        $this->assertStringNotContainsString('PATIENT_MARKER', $audit->after_payload);
        $this->assertSame($sourceRowsBefore, DB::table('source_import_rows')->count());
        $this->assertSame($sourceJobsBefore, DB::table('source_import_jobs')->count());
        $this->assertSame($filesBefore, DB::table('source_import_files')->count());
        $this->assertSame(0, DB::table('export_jobs')->count());
    }

    public function test_unauthorized_user_is_rejected_before_csv_or_audit(): void
    {
        $user = User::create([
            'name' => 'SOURCE_ERRORS_UNAUTHORIZED_TEST_ACCOUNT',
            'email' => 'source-errors-unauthorized@example.invalid',
            'password' => 'technical-test-password',
        ]);
        $jobId = $this->createSourceJob();
        $this->createSourceRow($jobId, 'invalid_identifier');

        $this->actingAs($user)
            ->get("/imports/source-files/{$jobId}/errors")
            ->assertForbidden();

        $this->assertDatabaseMissing('audit_logs', ['action' => 'source_import_error_exported']);
    }

    public function test_missing_job_uses_not_found_without_export_or_audit(): void
    {
        $user = $this->createAuthorizedUser('source-errors-missing@example.invalid');

        $this->actingAs($user)
            ->get('/imports/source-files/999999/errors')
            ->assertNotFound();

        $this->assertDatabaseMissing('audit_logs', ['action' => 'source_import_error_exported']);
    }

    public function test_existing_job_with_no_exportable_rows_returns_bom_header_only_and_audits_zero(): void
    {
        $user = $this->createAuthorizedUser('source-errors-empty@example.invalid');
        $jobId = $this->createSourceJob();
        $this->createSourceRow($jobId, 'valid', 'EMPTY_VALID_MARKER');

        $response = $this->actingAs($user)->get("/imports/source-files/{$jobId}/errors");

        $response->assertOk()->assertDownload("source-import-errors-job-{$jobId}.csv");
        $this->assertSame("\xEF\xBB\xBFsource_import_job_id,source_import_row_id,validation_status,error_code,safe_message\r\n", $response->streamedContent());
        $this->assertSame(0, DB::table('source_import_rows')->where('source_import_job_id', $jobId)->where('validation_status', '!=', 'valid')->count());
        $audit = DB::table('audit_logs')->where('action', 'source_import_error_exported')->sole();
        $payload = json_decode($audit->after_payload, true, flags: JSON_THROW_ON_ERROR);
        $this->assertSame(0, $payload['exported_error_count']);
    }

    public function test_repeated_export_is_live_read_only_and_creates_no_business_records(): void
    {
        $user = $this->createAuthorizedUser('source-errors-repeat@example.invalid');
        $jobId = $this->createSourceJob();
        $this->createSourceRow($jobId, 'invalid_identifier');
        $before = [
            'jobs' => DB::table('source_import_jobs')->count(),
            'files' => DB::table('source_import_files')->count(),
            'rows' => DB::table('source_import_rows')->count(),
            'exports' => DB::table('export_jobs')->count(),
        ];

        $first = $this->actingAs($user)->get("/imports/source-files/{$jobId}/errors");
        $second = $this->actingAs($user)->get("/imports/source-files/{$jobId}/errors");

        $this->assertSame($first->streamedContent(), $second->streamedContent());
        $this->assertSame($before['jobs'], DB::table('source_import_jobs')->count());
        $this->assertSame($before['files'], DB::table('source_import_files')->count());
        $this->assertSame($before['rows'], DB::table('source_import_rows')->count());
        $this->assertSame($before['exports'], DB::table('export_jobs')->count());
        $this->assertSame(2, DB::table('audit_logs')->where('action', 'source_import_error_exported')->count());
    }

    private function createAuthorizedUser(string $email): User
    {
        $user = User::create([
            'name' => 'SOURCE_ERRORS_AUTHORIZED_TEST_ACCOUNT',
            'email' => $email,
            'password' => 'technical-test-password',
        ]);
        $role = Role::create(['name' => 'source-errors-role-'.uniqid()]);
        $permission = Permission::firstOrCreate(['name' => 'import.source.view']);
        $user->roles()->attach($role);
        $role->permissions()->attach($permission);

        return $user;
    }

    private function createSourceJob(): int
    {
        return DB::table('source_import_jobs')->insertGetId([
            'job_name' => 'synthetic-source-error-export-job',
            'status' => 'preview_staged',
            'total_files' => 1,
            'total_rows' => 1,
            'valid_rows' => 0,
            'invalid_rows' => 1,
            'review_rows' => 1,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function createSourceRow(int $jobId, string $validationStatus, string $marker = 'SYNTHETIC_MARKER'): int
    {
        $fileId = DB::table('source_import_files')->where('source_import_job_id', $jobId)->value('id');
        if ($fileId === null) {
            $fileId = DB::table('source_import_files')->insertGetId([
                'source_import_job_id' => $jobId,
                'original_filename' => 'synthetic-errors.csv',
                'stored_path' => '__synthetic_no_file_stored__',
                'mime_type' => 'text/csv',
                'size_bytes' => 0,
                'sha256' => hash('sha256', 'synthetic-errors-'.$jobId),
                'row_count' => 0,
                'created_at' => now(),
                'updated_at' => now(),
            ]);
        }

        return DB::table('source_import_rows')->insertGetId([
            'source_import_job_id' => $jobId,
            'source_file_id' => $fileId,
            'row_number' => DB::table('source_import_rows')->where('source_import_job_id', $jobId)->count() + 1,
            'raw_payload' => json_encode(['marker' => $marker, 'raw_cid' => '1234567890123']),
            'raw_cid' => '1234567890123',
            'normalized_cid' => '1234567890123',
            'cid_status' => $validationStatus === 'valid' ? 'valid' : 'invalid',
            'raw_full_name' => 'PATIENT_NAME_MUST_NOT_EXPORT',
            'raw_service_text' => 'SYNTHETIC_SERVICE',
            'validation_status' => $validationStatus,
            'review_reason' => 'FREE_TEXT_REVIEW_REASON_MUST_NOT_EXPORT',
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }
}
