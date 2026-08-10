@extends('layouts.admin', ['title' => 'Target Group Review'])

@section('content')
    <h1>Target Group Review</h1>
    <p class="muted">Foundation review queue only. Durable import and history activation remain blocked.</p>

    @if (session('status'))
        <p class="status">{{ session('status') }}</p>
    @endif

    @if ($row !== null)
        <h2>Review Row {{ $row->id }}</h2>
        <dl>
            <dt>Review status</dt>
            <dd>{{ $row->review_status }}</dd>
            <dt>Reason</dt>
            <dd>{{ $row->review_reason_code ?? '[none]' }}</dd>
            <dt>CID</dt>
            <dd>{{ $row->masked_cid }}</dd>
            <dt>Name</dt>
            <dd>{{ $row->masked_name }}</dd>
            <dt>Birth date</dt>
            <dd>{{ $row->masked_birth_date }}</dd>
        </dl>

        @if ($row->authorized_identity !== null)
            <h3>Authorized Sensitive Identity</h3>
            <p>CID: {{ $row->authorized_identity['cid'] ?? '[missing]' }}</p>
            <p>Name: {{ $row->authorized_identity['name'] ?? '[missing]' }}</p>
            <p>Birth date: {{ $row->authorized_identity['birth_date'] ?? '[missing]' }}</p>
        @endif

        @if ($row->review_status === 'NEEDS_REVIEW')
            <form method="POST" action="{{ route('target-groups.review.approve', ['id' => $row->id]) }}">
                @csrf
                <label for="approve-reason">Approval reason</label>
                <select id="approve-reason" name="review_reason_code" required>
                    @foreach ($foundationReasons as $reason)
                        <option value="{{ $reason }}" @selected($reason === $row->review_reason_code)>{{ $reason }}</option>
                    @endforeach
                </select>
                <label for="approve-note">Operator note</label>
                <textarea id="approve-note" name="note" maxlength="2000"></textarea>
                <button type="submit">Approve review</button>
            </form>
            <form method="POST" action="{{ route('target-groups.review.reject', ['id' => $row->id]) }}">
                @csrf
                <label for="reject-reason">Rejection reason</label>
                <select id="reject-reason" name="review_reason_code" required>
                    @foreach ($foundationReasons as $reason)
                        <option value="{{ $reason }}" @selected($reason === $row->review_reason_code)>{{ $reason }}</option>
                    @endforeach
                </select>
                <label for="reject-note">Operator note</label>
                <textarea id="reject-note" name="note" maxlength="2000"></textarea>
                <button type="submit">Reject review</button>
            </form>
        @endif
    @endif

    <h2>Needs Review Queue</h2>
    @if ($rows->isEmpty())
        <p>No rows require review.</p>
    @else
        <table>
            <thead>
                <tr>
                    <th>Row</th>
                    <th>Status</th>
                    <th>Reason</th>
                    <th>Masked CID</th>
                    <th>Masked name</th>
                    <th>Detail</th>
                </tr>
            </thead>
            <tbody>
                @foreach ($rows as $reviewRow)
                    <tr>
                        <td>{{ $reviewRow->id }}</td>
                        <td>{{ $reviewRow->review_status }}</td>
                        <td>{{ $reviewRow->review_reason_code }}</td>
                        <td>{{ $reviewRow->masked_cid }}</td>
                        <td>{{ $reviewRow->masked_name }}</td>
                        <td><a href="{{ route('target-groups.review.show', ['id' => $reviewRow->id]) }}">View review</a></td>
                    </tr>
                @endforeach
            </tbody>
        </table>
    @endif

    <p>No durable target-group commit is available in this foundation slice.</p>
    <p>No cross-program or cross-hospital automatic matching is available.</p>
@endsection
