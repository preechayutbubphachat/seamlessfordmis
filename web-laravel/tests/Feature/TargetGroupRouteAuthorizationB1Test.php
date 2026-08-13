<?php

namespace Tests\Feature;

use App\Models\Permission;
use App\Models\Role;
use App\Models\User;
use Illuminate\Foundation\Http\Middleware\PreventRequestForgery;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;
use Tests\TestCase;

final class TargetGroupRouteAuthorizationB1Test extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutMiddleware(PreventRequestForgery::class);
    }

    /** @return array<string, string> */
    private function contract(): array
    {
        return [
            'GET /dashboard' => 'dashboard.view',
            'GET /target-groups' => 'targetgroup.view',
            'GET /target-groups/{id}' => 'targetgroup.view',
            'GET /target-groups/{id}/results' => 'targetgroup.result.view',
            'POST /target-groups/{id}/generate-results' => 'targetgroup.result.generate',
            'GET /settings/disease-services' => 'settings.disease.service.view',
            'GET /audit-logs' => 'audit.log.view',
            'GET /imports/source-files' => 'import.source.view',
            'GET /imports/source-files/{job}' => 'import.source.view',
            'GET /imports/source-files/preview' => 'import.source.preview',
            'POST /imports/source-files/preview' => 'import.source.preview',
            'POST /imports/source-files' => 'import.source.commit',
            'POST /imports/source-files/commit-preview' => 'import.source.commit',
            'GET /imports/target-groups' => 'import.targetgroup.view',
            'GET /imports/target-groups/{job}' => 'import.targetgroup.view',
            'GET /imports/target-groups/preview' => 'import.targetgroup.preview',
            'POST /imports/target-groups/preview' => 'import.targetgroup.preview',
            'POST /imports/target-groups' => 'import.targetgroup.commit',
            'POST /imports/target-groups/commit-preview' => 'import.targetgroup.commit',
            'GET /exports' => 'export.view',
            'GET /exports/preview' => 'export.preview',
            'POST /exports/preview' => 'export.preview',
            'POST /exports' => 'export.generate',
            'POST /exports/generate' => 'export.generate',
            'GET /exports/{exportJob}/download' => 'export.download',
            'GET /target-groups/review' => 'import.targetgroup.review.view',
            'GET /target-groups/review/{id}' => 'import.targetgroup.review.view',
            'POST /target-groups/review/{id}/approve' => 'import.targetgroup.review.approve',
            'POST /target-groups/review/{id}/reject' => 'import.targetgroup.review.reject',
        ];
    }

    public function test_all_b1_routes_have_exact_auth_and_permission_contract(): void
    {
        $routes = collect(Route::getRoutes())
            ->flatMap(function ($route): array {
                return collect($route->methods())
                    ->reject(fn (string $method): bool => $method === 'HEAD')
                    ->mapWithKeys(fn (string $method): array => [$method.' /'.$route->uri() => $route])
                    ->all();
            })
            ->filter(fn ($route, string $routeKey): bool => isset($this->contract()[$routeKey]))
            ->all();

        $this->assertCount(29, $routes);

        foreach ($this->contract() as $routeKey => $permission) {
            $this->assertArrayHasKey($routeKey, $routes, $routeKey);
            $middleware = $routes[$routeKey]->gatherMiddleware();
            $this->assertContains('auth', $middleware, $routeKey);
            $this->assertContains('permission:'.$permission, $middleware, $routeKey);
        }
    }

    public function test_guest_is_redirected_and_authenticated_users_without_exact_permission_are_forbidden(): void
    {
        $this->get('/dashboard')->assertRedirect(route('login'));

        $user = $this->createUser('no-permission');
        $this->actingAs($user)->get('/dashboard')->assertForbidden();

        $neighbor = $this->createUser('neighbor');
        $this->grant($neighbor, 'targetgroup.view');
        $this->actingAs($neighbor)->get('/dashboard')->assertForbidden();
    }

    public function test_exact_permission_reaches_each_foundation_route_without_changing_blocked_runtime(): void
    {
        $cases = [
            ['dashboard.view', 'get', '/dashboard', 200],
            ['targetgroup.view', 'get', '/target-groups', 200],
            ['targetgroup.result.view', 'get', '/target-groups/999/results', 200],
            ['targetgroup.result.generate', 'post', '/target-groups/999/generate-results', 302],
            ['settings.disease.service.view', 'get', '/settings/disease-services', 200],
            ['audit.log.view', 'get', '/audit-logs', 200],
            ['import.source.view', 'get', '/imports/source-files', 200],
            ['import.source.preview', 'get', '/imports/source-files/preview', 200],
            ['import.source.commit', 'post', '/imports/source-files/commit-preview', 302],
            ['import.targetgroup.view', 'get', '/imports/target-groups', 200],
            ['import.targetgroup.preview', 'get', '/imports/target-groups/preview', 200],
            ['import.targetgroup.commit', 'post', '/imports/target-groups', 501],
            ['export.view', 'get', '/exports', 200],
            ['export.preview', 'get', '/exports/preview', 200],
            ['export.generate', 'post', '/exports', 501],
        ];

        foreach ($cases as [$permission, $method, $uri, $status]) {
            $user = $this->createUser('authorized-'.str_replace('.', '-', $permission));
            $this->grant($user, $permission);
            $response = $this->actingAs($user)->{$method}($uri);
            $this->assertSame($status, $response->getStatusCode(), $permission.' '.$method.' '.$uri);
        }
    }

    public function test_read_permissions_do_not_grant_mutation_permissions_and_d6_remains_separate(): void
    {
        $readers = [
            ['targetgroup.view', 'post', '/target-groups/999/generate-results'],
            ['targetgroup.result.view', 'post', '/target-groups/999/generate-results'],
            ['import.source.view', 'post', '/imports/source-files/commit-preview'],
            ['import.source.preview', 'post', '/imports/source-files/commit-preview'],
            ['import.targetgroup.view', 'post', '/imports/target-groups'],
            ['import.targetgroup.preview', 'post', '/imports/target-groups'],
            ['export.view', 'post', '/exports/preview'],
            ['export.preview', 'post', '/exports/generate'],
            ['export.generate', 'get', '/exports/preview'],
            ['audit.targetgroup.view', 'get', '/audit-logs'],
        ];

        foreach ($readers as [$permission, $method, $uri]) {
            $user = $this->createUser('separation-'.str_replace('.', '-', $permission));
            $this->grant($user, $permission);
            $response = $this->actingAs($user)->{$method}($uri);
            $this->assertSame(403, $response->getStatusCode(), $permission.' '.$method.' '.$uri);
        }

        $reviewer = $this->createUser('d6-reviewer');
        $this->grant($reviewer, 'import.targetgroup.review.view');
        $this->actingAs($reviewer)->get('/target-groups/review')->assertOk();
        $this->actingAs($reviewer)->get('/target-groups')->assertForbidden();
    }

    public function test_d7_d8_routes_are_absent_and_target_group_commit_does_not_persist(): void
    {
        $this->assertNull(Route::getRoutes()->getByName('target-groups.versions'));
        $this->assertNull(Route::getRoutes()->getByName('target-groups.reconcile'));

        $user = $this->createUser('target-commit');
        $this->grant($user, 'import.targetgroup.commit');
        $this->actingAs($user)->post('/imports/target-groups', [
            'files' => [],
        ])->assertStatus(501);

        $this->assertSame(0, DB::table('target_group_jobs')->count());
        $this->assertSame(0, DB::table('target_group_history_rows')->count());
    }

    private function createUser(string $suffix): User
    {
        return User::create([
            'name' => 'SYNTHETIC_B1_'.$suffix,
            'email' => $suffix.'@example.invalid',
            'password' => 'technical-test-password',
        ]);
    }

    private function grant(User $user, string ...$permissions): void
    {
        $role = Role::create([
            'name' => 'synthetic-b1-'.$user->id,
            'display_name' => 'Synthetic B1 role',
        ]);
        $user->roles()->attach($role);

        foreach ($permissions as $permissionName) {
            $permission = Permission::firstOrCreate(['name' => $permissionName]);
            $role->permissions()->attach($permission);
        }
    }
}
