@extends('layouts.admin', ['title' => $title])

@section('content')
    <h1>{{ $title }}</h1>
    <p class="muted">{{ $safetyNote }}</p>
    @if($importType === 'target_group')
        <p class="muted">การแสดงตัวอย่าง Target Group เป็นแบบอ่านอย่างเดียว การนำเข้าแบบถาวรยังไม่เปิดใช้งาน</p>
    @else
        <p class="muted">CSV preview uses a temporary server-side token. Commit requires explicit confirmation and does not store the uploaded file.</p>
    @endif

    @if($errors->any())
        <div class="empty-state">
            @foreach($errors->all() as $error)
                <div>{{ $error }}</div>
            @endforeach
        </div>
    @endif

    <form method="POST" action="{{ route($postRoute) }}" enctype="multipart/form-data" style="margin-top: 18px;">
        @csrf
        <label for="file">CSV file</label>
        <input id="file" name="file" type="file" accept=".csv,text/csv" required>
        <button type="submit">Preview</button>
    </form>

    @if($preview !== null)
        <h2>Preview Summary</h2>
        <table style="width: 100%; border-collapse: collapse; margin-top: 12px;">
            <tbody>
                <tr><th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Total Rows</th><td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $preview['total_rows'] }}</td></tr>
                <tr><th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Valid Rows</th><td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $preview['valid_rows'] }}</td></tr>
                <tr><th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Invalid Rows</th><td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $preview['invalid_rows'] }}</td></tr>
                <tr><th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Missing Identifier Rows</th><td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $preview['missing_identifier_rows'] }}</td></tr>
            </tbody>
        </table>

        @if(!empty($preview['header_mapping']))
        <h2>Header Mapping</h2>
        <table style="width: 100%; border-collapse: collapse; margin-top: 12px;">
            <thead>
                <tr>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Source Header</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Canonical Field</th>
                    <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Status</th>
                </tr>
            </thead>
            <tbody>
                @foreach($preview['header_mapping'] as $source => $canonical)
                    <tr>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $source }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $canonical ?? 'unrecognized' }}</td>
                        <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $canonical ? 'recognized' : 'ignored' }}</td>
                    </tr>
                @endforeach
            </tbody>
        </table>
        @endif

        @if($preview['errors'] !== [])
            <h2>Preview Errors</h2>
            <pre>{{ json_encode($preview['errors'], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) }}</pre>
            <button type="button" disabled>Commit disabled until preview errors are fixed</button>
        @elseif($previewToken)
            @if($importType === 'target_group')
                <h2>Durable Commit Unavailable</h2>
                <p class="muted">การนำเข้า Target Group แบบถาวรยังไม่ Implement การแสดงตัวอย่างนี้จะไม่สร้างข้อมูลถาวร</p>
                <p class="muted">DURABLE_COMMIT_AVAILABLE: NO</p>
            @else
                <h2>Commit Preview To Staging</h2>
                <p class="muted">This writes preview rows to staging only. It does not create results, exports, or stored upload files.</p>
                <form method="POST" action="{{ route($commitRoute) }}">
                    @csrf
                    <input type="hidden" name="preview_token" value="{{ $previewToken }}">
                    <input type="hidden" name="import_type" value="{{ $importType }}">
                    <label>
                        <input type="checkbox" name="confirmed" value="1" required>
                        I confirm this is synthetic/dev preview data and should be staged.
                    </label>
                    <button type="submit">Commit Preview To Staging</button>
                </form>
            @endif
        @endif

        @if($preview['rows'] === [])
            <div class="empty-state">No preview rows available</div>
        @else
            <h2>Preview Rows</h2>
            <table style="width: 100%; border-collapse: collapse; margin-top: 12px;">
                <thead>
                    <tr>
                        <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Row</th>
                        <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">CID Status</th>
                        <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Raw CID</th>
                        <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Normalized CID</th>
                        <th style="text-align: left; border-bottom: 1px solid var(--border); padding: 8px;">Raw Payload Preview</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach($preview['rows'] as $row)
                        <tr>
                            <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $row['row_number'] }}</td>
                            <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $row['identifier_status'] }}</td>
                            <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $row['raw_cid'] ?? 'missing' }}</td>
                            <td style="border-bottom: 1px solid var(--border); padding: 8px;">{{ $row['normalized_cid'] ?? 'none' }}</td>
                            <td style="border-bottom: 1px solid var(--border); padding: 8px;"><pre style="white-space: pre-wrap; margin: 0;">{{ json_encode($row['raw_payload'], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) }}</pre></td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        @endif
    @endif
@endsection
