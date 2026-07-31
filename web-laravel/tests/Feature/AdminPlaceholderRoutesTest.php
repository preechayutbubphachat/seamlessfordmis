<?php

namespace Tests\Feature;

use Tests\TestCase;

final class AdminPlaceholderRoutesTest extends TestCase
{
    public function test_root_redirects_to_dashboard_placeholder(): void
    {
        $this->get('/')->assertRedirect('/dashboard');

        $this->get('/dashboard')
            ->assertOk()
            ->assertSee('Dashboard')
            ->assertSee('No real patient data');
    }
}
