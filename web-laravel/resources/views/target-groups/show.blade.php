@extends('layouts.admin', ['title' => 'Target Group Detail'])

@section('content')
    <h1>Target Group Detail</h1>
    <p class="muted">Controlled result generation reads staged target group rows only.</p>
    <p class="muted">No upload, parser, export, fuzzy matching, edit, or delete action is available here.</p>

    @if($errors->any())
        <div class="empty-state">
            @foreach($errors->all() as $error)
                <div>{{ $error }}</div>
            @endforeach
        </div>
    @endif

    @if($targetGroupJob === null)
        <div class="empty-state">No target group job found</div>
    @else
        <h2>Staging Summary</h2>
        <table style="width: 100%; border-collapse: collapse; margin-top: 12px;">
            <tbody>
                <tr><th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Job ID</th><td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $targetGroupJob->id }}</td></tr>
                <tr><th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Status</th><td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $targetGroupJob->status }}</td></tr>
                <tr><th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Staged Rows</th><td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $rowCount }}</td></tr>
            </tbody>
        </table>

        <h2>Generate Result Drafts</h2>
        <p class="muted">Select service keys explicitly. Latest history dates are limited to the selected services.</p>

        <form method="POST" action="{{ route('target-groups.generate-results', ['id' => $targetGroupJob->id]) }}">
            @csrf

            @if($services->isNotEmpty())
                @foreach($services as $service)
                    <label style="display: block; margin: 6px 0;">
                        <input type="checkbox" name="selected_service_keys[]" value="{{ $service->service_key }}">
                        {{ $service->service_key }} - {{ $service->display_name }}
                    </label>
                @endforeach
            @else
                <label for="selected-service-key">Selected service key</label>
                <input id="selected-service-key" name="selected_service_keys[]" type="text" placeholder="synthetic_service_key">
            @endif

            <label style="display: block; margin-top: 12px;">
                <input type="checkbox" name="confirmed" value="1" required>
                I confirm result generation should read staged data only.
            </label>

            <button type="submit">Generate Result Drafts</button>
        </form>
    @endif
@endsection
