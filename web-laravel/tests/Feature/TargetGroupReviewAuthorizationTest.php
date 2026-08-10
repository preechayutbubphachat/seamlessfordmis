<?php

namespace Tests\Feature;

use App\Models\Permission;
use App\Models\Role;
use App\Models\TargetGroupRow;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class TargetGroupReviewAuthorizationTest extends TestCase
{
    use RefreshDatabase;

    public function test_guest_and_user_without_permission_are_denied(): void
    {
        $this->get('/target-groups/review')->assertRedirect(route('login'));

        $user = $this->createUser('no-permission');
        $this->actingAs($user)->get('/target-groups/review')->assertForbidden();
    }

    public function test_review_queue_is_permission_guarded_and_masks_sensitive_identity(): void
    {
        $user = $this->createUser('review-viewer');
        $this->grant($user, 'import.targetgroup.review.view');
        $this->createRow();

        $this->actingAs($user)
            ->get('/target-groups/review')
            ->assertOk()
            ->assertSee('Target Group Review')
            ->assertSee('*********0121')
            ->assertDontSee('1234567890121')
            ->assertDontSee('SYNTHETIC_NAME');
    }

    public function test_sensitive_identity_requires_a_separate_permission(): void
    {
        $viewer = $this->createUser('review-viewer-only');
        $this->grant($viewer, 'import.targetgroup.review.view');
        $row = $this->createRow();

        $this->actingAs($viewer)
            ->get('/target-groups/review/'.$row->id)
            ->assertOk()
            ->assertDontSee('1234567890121');

        $identityViewer = $this->createUser('identity-viewer');
        $this->grant($identityViewer, 'import.targetgroup.review.view', 'import.targetgroup.identity.view');

        $this->actingAs($identityViewer)
            ->get('/target-groups/review/'.$row->id)
            ->assertOk()
            ->assertSee('1234567890121');
    }

    public function test_approve_action_requires_approve_permission_and_has_no_durable_import_effect(): void
    {
        $viewer = $this->createUser('approve-viewer');
        $this->grant($viewer, 'import.targetgroup.review.view');
        $row = $this->createRow();
        DB::table('target_group_rows')->where('id', $row->id)->update([
            'review_status' => 'NEEDS_REVIEW',
            'review_reason_code' => 'NAME_CONFLICT',
        ]);

        $this->actingAs($viewer)
            ->post('/target-groups/review/'.$row->id.'/approve', [
                'review_reason_code' => 'NAME_CONFLICT',
                'note' => 'Synthetic approval attempt without permission.',
            ])
            ->assertForbidden();

        $this->assertSame('NEEDS_REVIEW', DB::table('target_group_rows')->where('id', $row->id)->value('review_status'));
    }

    private function createUser(string $suffix): User
    {
        return User::create([
            'name' => 'SYNTHETIC_'.$suffix,
            'email' => $suffix.'@example.invalid',
            'password' => 'technical-test-password',
        ]);
    }

    private function grant(User $user, string ...$permissions): void
    {
        $role = Role::create(['name' => 'synthetic-'.$user->id, 'display_name' => 'Synthetic reviewer']);
        $user->roles()->attach($role);

        foreach ($permissions as $permissionName) {
            $permission = Permission::firstOrCreate(['name' => $permissionName]);
            $role->permissions()->attach($permission);
        }
    }

    private function createRow(): TargetGroupRow
    {
        $jobId = DB::table('target_group_jobs')->insertGetId([
            'group_name' => 'SYNTHETIC_REVIEW_GROUP',
            'status' => 'staged',
            'total_files' => 1,
            'total_rows' => 1,
            'valid_rows' => 0,
            'invalid_rows' => 1,
            'review_rows' => 1,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        $fileId = DB::table('target_group_files')->insertGetId([
            'target_group_job_id' => $jobId,
            'original_filename' => 'synthetic.csv',
            'stored_path' => 'synthetic/synthetic.csv',
            'mime_type' => 'text/csv',
            'size_bytes' => 1,
            'sha256' => hash('sha256', 'synthetic-'.$jobId),
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return TargetGroupRow::query()->create([
            'target_group_job_id' => $jobId,
            'target_group_file_id' => $fileId,
            'sheet_name' => 'SYNTHETIC',
            'row_number' => 1,
            'raw_payload' => ['source' => 'synthetic-test'],
            'raw_cid' => '1234567890121',
            'normalized_cid' => '1234567890121',
            'cid_status' => 'valid',
            'raw_full_name' => 'SYNTHETIC_NAME',
            'normalized_full_name' => 'SYNTHETIC_NAME',
            'raw_birth_date' => '2000-01-01',
            'normalized_birth_date' => '2000-01-01',
            'validation_status' => 'invalid',
            'review_reason' => 'Synthetic conflict',
            'review_status' => 'NEEDS_REVIEW',
            'review_reason_code' => 'NAME_CONFLICT',
        ]);
    }
}
