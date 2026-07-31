@extends('layouts.admin', ['title' => $title])

@section('content')
    <h1>{{ $title }}</h1>
    <p class="muted">{{ $safetyNote }}</p>
    <p class="muted">Review only. No commit import, matching, result generation, export, edit, or delete action is available.</p>

    @if($jobs->isEmpty())
        <div class="empty-state">{{ $emptyMessage }}</div>
    @else
        <table style="width: 100%; border-collapse: collapse; margin-top: 12px;">
            <thead>
                <tr>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Job ID</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Status</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Created By</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Created At</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Rows</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Review</th>
                </tr>
            </thead>
            <tbody>
                @foreach($jobs as $job)
                    <tr>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $job->id }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $job->status }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $job->created_by_user_id ?? 'system' }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $job->created_at }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">
                            total {{ $job->total_rows }} /
                            valid {{ $job->valid_rows }} /
                            invalid {{ $job->invalid_rows }} /
                            review {{ $job->review_rows }}
                        </td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">
                            <a href="{{ route($detailRoute, ['job' => $job->id]) }}">View rows</a>
                        </td>
                    </tr>
                @endforeach
            </tbody>
        </table>
    @endif
@endsection
