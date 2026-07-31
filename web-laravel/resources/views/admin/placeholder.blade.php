@extends('layouts.admin', ['title' => $page['title']])

@section('content')
    <h1>{{ $page['title'] }}</h1>
    <p class="muted">{{ $page['workflow'] }}</p>

    @isset($page['context'])
        <p class="muted">{{ $page['context'] }}</p>
    @endisset

    <h2>Intended Workflow</h2>
    <p>This page is reserved for a future guarded workflow after the required validation, staging, preview, and audit controls are implemented.</p>

    <h2>Safety Notes</h2>
    <p>No real patient data.</p>
    <p>No upload form is available in this placeholder.</p>
    <p>No fake patient or sample patient data is displayed.</p>
    <p>No records loaded.</p>

    <div class="empty-state">
        Placeholder only. This screen does not read, write, import, match, generate, export, or seed data.
    </div>
@endsection
