<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\RateLimiter;
use Tests\TestCase;

final class AuthenticationFlowTest extends TestCase
{
    use RefreshDatabase;

    protected function tearDown(): void
    {
        RateLimiter::clear('auth-test@example.invalid|127.0.0.1');
        parent::tearDown();
    }

    public function test_login_page_contains_only_the_staff_session_login_form(): void
    {
        $this->get('/login')
            ->assertOk()
            ->assertSee('Staff sign in')
            ->assertSee('name="email"', false)
            ->assertSee('type="password"', false)
            ->assertSee('autocomplete="current-password"', false)
            ->assertSee('name="_token"', false)
            ->assertDontSee('Register')
            ->assertDontSee('default password');

        $this->assertTrue(route('login') !== '');
    }

    public function test_valid_credentials_authenticate_regenerate_session_and_redirect_internally(): void
    {
        $user = $this->createUser();
        $this->withSession(['technical_marker' => 'before-login']);
        $oldSessionId = session()->getId();

        $this->post('/login', [
            'email' => 'auth-test@example.invalid',
            'password' => 'technical-test-password',
        ])->assertRedirect(route('admin.dashboard'));

        $this->assertAuthenticatedAs($user);
        $this->assertNotSame($oldSessionId, session()->getId());
    }

    public function test_invalid_credentials_fail_generically_without_echoing_password(): void
    {
        $this->createUser();
        $response = $this->from('/login')->post('/login', [
            'email' => 'auth-test@example.invalid',
            'password' => 'TECHNICAL_SECRET_MUST_NOT_RENDER',
        ]);

        $response->assertRedirect('/login')
            ->assertSessionHasErrors(['email'])
            ->assertDontSee('TECHNICAL_SECRET_MUST_NOT_RENDER');
        $this->assertGuest();
    }

    public function test_login_is_rate_limited_after_five_failed_attempts(): void
    {
        for ($attempt = 1; $attempt <= 5; $attempt++) {
            $this->from('/login')->post('/login', [
                'email' => 'auth-test@example.invalid',
                'password' => 'technical-invalid-password',
            ])->assertSessionHasErrors('email');
        }

        $this->from('/login')->post('/login', [
            'email' => 'auth-test@example.invalid',
            'password' => 'technical-invalid-password',
        ])->assertSessionHasErrors([
            'email' => 'Too many login attempts. Please try again later.',
        ]);
    }

    public function test_authenticated_user_is_redirected_away_from_login(): void
    {
        $this->actingAs($this->createUser())
            ->get('/login')
            ->assertRedirect(route('admin.dashboard'));
    }

    public function test_authenticated_logout_invalidates_session_and_regenerates_csrf_token(): void
    {
        $user = $this->createUser();
        $this->actingAs($user)->withSession(['technical_marker' => 'before-logout']);
        $oldToken = session()->token();

        $this->post('/logout')->assertRedirect(route('login'));

        $this->assertGuest();
        $this->assertFalse(session()->has('technical_marker'));
        $this->assertNotSame($oldToken, session()->token());
    }

    public function test_guest_logout_redirects_to_login_and_forbidden_public_auth_routes_are_absent(): void
    {
        $this->post('/logout')->assertRedirect(route('login'));
        $this->get('/logout')->assertMethodNotAllowed();
        $this->get('/register')->assertNotFound();
        $this->post('/register')->assertNotFound();
        $this->get('/forgot-password')->assertNotFound();
        $this->get('/reset-password/technical-token')->assertNotFound();
    }

    private function createUser(): User
    {
        return User::create([
            'name' => 'AUTH_TEST_ACCOUNT',
            'email' => 'auth-test@example.invalid',
            'password' => 'technical-test-password',
        ]);
    }
}
