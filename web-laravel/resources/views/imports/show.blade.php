@extends('layouts.admin', ['title' => $title])

@section('content')
    <h1>{{ $title }}</h1>
    <p class="muted">{{ $safetyNote }}</p>

    @if($job)
        <h2>Job Metadata</h2>
        <table style="width: 100%; border-collapse: collapse; margin-top: 12px;">
            <tbody>
                <tr>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Job ID</th>
                    <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $job->id }}</td>
                </tr>
                <tr>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Status</th>
                    <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $job->status }}</td>
                </tr>
                <tr>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Created By</th>
                    <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $job->created_by_user_id ?? 'system' }}</td>
                </tr>
                <tr>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Created At</th>
                    <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $job->created_at }}</td>
                </tr>
            </tbody>
        </table>
    @endif

    @if($rows->isEmpty())
        <div class="empty-state">{{ $emptyMessage }}. {{ $legacyEmptyMessage }}</div>
    @else
        <h2>Staged Rows</h2>
        <table style="width: 100%; border-collapse: collapse; margin-top: 12px;">
            <thead>
                <tr>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Row</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">CID Status</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Validation</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Raw CID</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Normalized CID</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Raw Fields</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Raw Payload Preview</th>
                </tr>
            </thead>
            <tbody>
                @foreach($rows as $row)
                    <tr>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $row->row_number }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $row->cid_status }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $row->validation_status }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $row->raw_cid ?? 'missing' }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $row->normalized_cid ?? 'none' }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">
                            @foreach($rawFields as $label => $field)
                                <div>{{ $label }}: {{ $row->{$field} ?? 'none' }}</div>
                            @endforeach
                        </td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">
                            <pre style="white-space: pre-wrap; margin: 0;">{{ json_encode(json_decode($row->raw_payload, true) ?: [], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) }}</pre>
                        </td>
                    </tr>
                @endforeach
            </tbody>
        </table>
    @endif
@endsection
