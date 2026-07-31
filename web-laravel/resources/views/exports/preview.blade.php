@extends('layouts.admin', ['title' => 'Export Preview'])

@section('content')
    <h1>Export Eligibility Preview</h1>
    <p class="muted">Export file generation is not enabled yet.</p>
    <p class="muted">Preview reads persisted target_group_results only. It does not read staging rows, upload payloads, or preview sessions.</p>

    @if(!empty($eligibilityError))
        <div class="empty-state">Preview unavailable: {{ $eligibilityError }}</div>
    @endif

    <h2>Read-only Preview Filter</h2>
    <form method="post" action="{{ route('exports.preview.store') }}">
        @csrf
        <div style="display: grid; gap: 12px; max-width: 520px;">
            <label>
                Target group job id
                <input name="target_group_job_id" value="{{ old('target_group_job_id') }}" inputmode="numeric" style="width: 100%; padding: 8px; border: 1px solid var(--border); border-radius: 6px;">
            </label>
            @error('target_group_job_id')
                <div class="muted">{{ $message }}</div>
            @enderror

            <label>
                Result generation job id
                <input name="result_generation_job_id" value="{{ old('result_generation_job_id') }}" inputmode="numeric" style="width: 100%; padding: 8px; border: 1px solid var(--border); border-radius: 6px;">
            </label>
            @error('result_generation_job_id')
                <div class="muted">{{ $message }}</div>
            @enderror

            <fieldset style="border: 1px solid var(--border); border-radius: 6px; padding: 10px;">
                <legend>Optional category filters</legend>
                @foreach($categories as $category)
                    <label style="display: block; margin: 6px 0;">
                        <input type="checkbox" name="categories[]" value="{{ $category }}" @checked(in_array($category, old('categories', []), true))>
                        {{ $category }}
                    </label>
                @endforeach
            </fieldset>
            @error('categories')
                <div class="muted">{{ $message }}</div>
            @enderror
            @error('categories.*')
                <div class="muted">{{ $message }}</div>
            @enderror

            <button type="submit" style="width: fit-content; padding: 8px 12px;">Preview eligibility</button>
        </div>
    </form>

    @if($preview)
        <h2>Aggregate Preview</h2>
        <p class="muted">{{ $preview['warning'] }}</p>
        <table style="width: 100%; border-collapse: collapse; margin-top: 12px;">
            <tbody>
                <tr>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">target_group_job_id</th>
                    <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $preview['target_group_job_id'] }}</td>
                </tr>
                <tr>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">result_generation_job_id</th>
                    <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $preview['result_generation_job_id'] ?? 'all stored result jobs for target group' }}</td>
                </tr>
                <tr>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">eligibility_status</th>
                    <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $preview['eligibility_status'] }}</td>
                </tr>
                <tr>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">eligibility_reason</th>
                    <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $preview['eligibility_reason'] }}</td>
                </tr>
                <tr>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">total stored result row count</th>
                    <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $preview['total_stored_result_rows'] }}</td>
                </tr>
                <tr>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">result source/provenance availability count</th>
                    <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $preview['result_source_provenance_count'] }}</td>
                </tr>
                <tr>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">results with provenance count</th>
                    <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $preview['results_with_provenance_count'] }}</td>
                </tr>
                <tr>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">results without provenance count</th>
                    <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $preview['results_without_provenance_count'] }}</td>
                </tr>
            </tbody>
        </table>

        <h2>Category Counts</h2>
        <table style="width: 100%; border-collapse: collapse; margin-top: 12px;">
            <thead>
                <tr>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Category</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Count</th>
                </tr>
            </thead>
            <tbody>
                @foreach($preview['category_counts'] as $category => $count)
                    <tr>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $category }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $count }}</td>
                    </tr>
                @endforeach
            </tbody>
        </table>

        <h2>Selected Filter Summary</h2>
        <pre>{{ json_encode($preview['selected_filter_summary'], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) }}</pre>
    @else
        <div class="empty-state">No export preview loaded</div>
    @endif
@endsection
