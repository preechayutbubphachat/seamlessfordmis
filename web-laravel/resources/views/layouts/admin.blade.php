<!DOCTYPE html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ $title ?? 'Admin Placeholder' }} - {{ config('app.name', 'SeamlessFordMIS') }}</title>
    <style>
        :root {
            color-scheme: light;
            --bg: #f6f7f9;
            --panel: #ffffff;
            --text: #17202a;
            --muted: #5f6b7a;
            --border: #d9dee7;
            --nav: #223044;
            --nav-active: #ffffff;
            --safety: #fff7d6;
            --safety-border: #d9b44a;
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            background: var(--bg);
            color: var(--text);
            font-family: Arial, Helvetica, sans-serif;
            line-height: 1.5;
        }

        .shell {
            min-height: 100vh;
            display: grid;
            grid-template-columns: 260px 1fr;
        }

        .sidebar {
            background: var(--nav);
            color: #dfe7f3;
            padding: 24px 18px;
        }

        .brand {
            font-size: 18px;
            font-weight: 700;
            margin-bottom: 24px;
        }

        .nav-section {
            margin-top: 18px;
            color: #9fb0c5;
            font-size: 12px;
            text-transform: uppercase;
        }

        .nav-link {
            display: block;
            padding: 9px 10px;
            margin: 3px 0;
            color: inherit;
            text-decoration: none;
            border-radius: 6px;
        }

        .nav-link:hover,
        .nav-link.active {
            background: rgba(255, 255, 255, 0.12);
            color: var(--nav-active);
        }

        .main {
            padding: 28px;
        }

        .safety-banner {
            border: 1px solid var(--safety-border);
            background: var(--safety);
            padding: 14px 16px;
            border-radius: 8px;
            margin-bottom: 22px;
            font-size: 14px;
        }

        .content {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 24px;
            max-width: 980px;
        }

        h1 {
            font-size: 28px;
            margin: 0 0 12px;
        }

        h2 {
            font-size: 16px;
            margin: 24px 0 8px;
        }

        p {
            margin: 0 0 10px;
        }

        .muted {
            color: var(--muted);
        }

        .empty-state {
            margin-top: 18px;
            border: 1px dashed var(--border);
            border-radius: 8px;
            padding: 18px;
            color: var(--muted);
            background: #fbfcfd;
        }

        @media (max-width: 820px) {
            .shell {
                grid-template-columns: 1fr;
            }

            .sidebar {
                padding: 18px;
            }

            .main {
                padding: 18px;
            }
        }
    </style>
</head>
<body>
    <div class="shell">
        <aside class="sidebar" aria-label="Admin navigation">
            <div class="brand">SeamlessFordMIS</div>

            <div class="nav-section">Overview</div>
            <a class="nav-link @if(request()->is('dashboard')) active @endif" href="{{ route('admin.dashboard') }}">Dashboard</a>

            <div class="nav-section">Imports</div>
            <a class="nav-link @if(request()->is('imports/source-files')) active @endif" href="{{ route('imports.source-files') }}">Source Files</a>
            <a class="nav-link @if(request()->is('imports/target-groups')) active @endif" href="{{ route('imports.target-groups') }}">Target Group Imports</a>

            <div class="nav-section">Target Groups</div>
            <a class="nav-link @if(request()->is('target-groups')) active @endif" href="{{ route('target-groups.index') }}">Target Groups</a>
            <a class="nav-link @if(request()->is('target-groups/*/results')) active @endif" href="{{ route('target-groups.results', ['id' => 1]) }}">Results Placeholder</a>

            <div class="nav-section">Operations</div>
            <a class="nav-link @if(request()->is('exports')) active @endif" href="{{ route('exports.index') }}">Exports</a>
            <a class="nav-link @if(request()->is('settings/disease-services')) active @endif" href="{{ route('settings.disease-services') }}">Disease Services</a>
            <a class="nav-link @if(request()->is('audit-logs')) active @endif" href="{{ route('audit-logs.index') }}">Audit Logs</a>
        </aside>

        <main class="main">
            <div class="safety-banner">
                W3 placeholder only. No real patient data. No upload form, parser, matching, result generation, export execution, or seeded users.
            </div>

            <section class="content">
                @yield('content')
            </section>
        </main>
    </div>
</body>
</html>
