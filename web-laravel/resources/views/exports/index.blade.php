@extends('layouts.admin', ['title' => 'Exports'])

@section('content')
    <h1>Exports</h1>
    <p class="muted">Export generation is not enabled yet for public access or download.</p>
    <p class="muted">Private exports read from persisted target_group_results only and never fake output.</p>
    <p><a href="{{ route('exports.preview') }}">Open read-only export eligibility preview</a></p>

    @if(session('status'))
        <div class="safety-banner" role="status">{{ session('status') }}</div>
    @endif

    @if($errors->has('export'))
        <div class="safety-banner" role="alert">{{ $errors->first('export') }}</div>
    @endif

    @auth
        @if(auth()->user()->hasPermission('export.generate'))
            <h2>Generate private deidentified CSV</h2>
            <div class="safety-banner">
                Policy: <strong>deidentified_internal_v1</strong>. The artifact contains no CID, name, birth date,
                review_reason, or raw_payload. Generation uses persisted results only, stores the artifact privately,
                and does not enable download.
            </div>

            @if($errors->any())
                <div class="safety-banner" role="alert">
                    @foreach($errors->all() as $error)
                        <div>{{ $error }}</div>
                    @endforeach
                </div>
            @endif

            <form method="POST" action="{{ route('exports.generate') }}">
                @csrf
                <label for="target_group_job_id">Target group job ID</label>
                <input id="target_group_job_id" name="target_group_job_id" type="number" min="1" value="{{ old('target_group_job_id') }}" required>

                <label for="result_generation_job_id">Result generation job ID</label>
                <input id="result_generation_job_id" name="result_generation_job_id" type="number" min="1" value="{{ old('result_generation_job_id') }}" required>

                <fieldset style="margin-top: 16px;">
                    <legend>Result categories (leave all unchecked to include every allowed category)</legend>
                    @foreach(\App\Services\Export\ExportService::RESULT_CATEGORIES as $category)
                        <label style="display: block;">
                            <input name="categories[]" type="checkbox" value="{{ $category }}" @checked(in_array($category, old('categories', []), true))>
                            {{ $category }}
                        </label>
                    @endforeach
                </fieldset>

                <label style="display: block; margin-top: 16px;">
                    <input name="confirmed" type="checkbox" value="1" required>
                    I confirm generation of a private deidentified artifact from persisted results.
                </label>

                <button type="submit" style="margin-top: 16px;">Generate private CSV</button>
            </form>
        @endif
    @endauth

    @if($exportJobs->isEmpty())
        <div class="empty-state">No export jobs yet</div>
    @else
        <h2>Export Jobs</h2>
        <table style="width: 100%; border-collapse: collapse; margin-top: 12px;">
            <thead>
                <tr>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">ID</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Type</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Status</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Filters</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Rows</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Bytes</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">SHA-256</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Finished</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Failure</th>
                </tr>
            </thead>
            <tbody>
                @foreach($exportJobs as $job)
                    <tr>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $job->id }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $job->export_type }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $job->status }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;"><pre>{{ json_encode(json_decode($job->filters, true) ?: [], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) }}</pre></td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $job->row_count ?? '—' }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $job->byte_count ?? '—' }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px; font-family: monospace; word-break: break-all;">{{ $job->sha256 ?? '—' }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $job->finished_at ?? '—' }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $job->error_message ?? '—' }}</td>
                    </tr>
                @endforeach
            </tbody>
        </table>
    @endif
@endsection
