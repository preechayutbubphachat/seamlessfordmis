@extends('layouts.admin', ['title' => 'Target Group Results'])

@section('content')
    <h1>Target Group Results</h1>
    <p class="muted">Read-only review of stored result drafts for target group job {{ $targetGroupJobId }}.</p>
    <p class="muted">No import, upload, matching, edit, delete, or export action is available on this page.</p>

    @if($results->isEmpty())
        <div class="empty-state">No stored results yet</div>
    @else
        <h2>Stored Results</h2>
        <table style="width: 100%; border-collapse: collapse; margin-top: 12px;">
            <thead>
                <tr>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Category</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Review</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Latest Date</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Latest Source</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Evidence</th>
                </tr>
            </thead>
            <tbody>
                @foreach($results as $result)
                    <tr>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $result->result_category }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">
                            <div>{{ $result->review_status }}</div>
                            @if($result->review_reason)
                                <div class="muted">{{ $result->review_reason }}</div>
                            @endif
                        </td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $result->latest_history_date ?? 'None' }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $result->latest_history_source ?? 'None' }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">
                            @forelse(($result->evidence_summary_decoded['sources'] ?? []) as $summarySource)
                                <div>{{ $summarySource['source_type'] ?? 'unknown_source' }}</div>
                                @if(isset($summarySource['provenance']))
                                    <pre>{{ json_encode($summarySource['provenance'], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) }}</pre>
                                @endif
                            @empty
                                <span class="muted">No evidence summary</span>
                            @endforelse
                        </td>
                    </tr>
                    @if($result->sources->isNotEmpty())
                        <tr>
                            <td colspan="5" style="border-bottom: 1px solid var(--border); padding: 8px;">
                                <h2>Evidence / Provenance Detail</h2>
                                @foreach($result->sources as $source)
                                    <div class="empty-state">
                                        <p><strong>Source type:</strong> {{ $source->source_type }}</p>
                                        <p><strong>Service:</strong> {{ $source->normalized_service_key ?? 'None' }}</p>
                                        <p><strong>Evidence date:</strong> {{ $source->evidence_date ?? 'None' }}</p>
                                        <p><strong>Source payload:</strong></p>
                                        <pre>{{ json_encode($source->source_payload_decoded, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) }}</pre>
                                        <p><strong>Provenance:</strong></p>
                                        <pre>{{ json_encode($source->provenance_decoded, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) }}</pre>
                                    </div>
                                @endforeach
                            </td>
                        </tr>
                    @endif
                @endforeach
            </tbody>
        </table>
    @endif
@endsection
