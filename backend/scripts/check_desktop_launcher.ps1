# ============================================================
# D3.1 Windows Desktop Launcher Validation (PowerShell)
# Called via check_desktop_launcher.bat
# Safe: no Docker, no patient data, no destructive action
# ============================================================
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Resolve-Path (Join-Path $ScriptDir "..")
$RootDir = Resolve-Path (Join-Path $BackendDir "..")

Write-Host "SeamlessFordMIS Desktop Launcher Check (D3.1)"
Write-Host "Root: $RootDir"
Write-Host "Backend: $BackendDir"
Set-Location $BackendDir

$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (!(Test-Path $PythonExe)) {
    Write-Host "WARN: .venv not found, falling back to system python"
    $PythonExe = "python"
}
Write-Host "Using Python: $PythonExe"

# Visibility: pre-existing port state
$existing = Get-NetTCPConnection -LocalPort 8010 -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "WARN: Port 8010 is already in use before launcher start"
    $existing | Format-Table -AutoSize
}

$outLog = Join-Path $env:TEMP "sfmis_launcher_stdout.log"
$errLog = Join-Path $env:TEMP "sfmis_launcher_stderr.log"
Remove-Item $outLog, $errLog -ErrorAction SilentlyContinue

Write-Host "Starting launcher..."
$proc = Start-Process `
    -FilePath $PythonExe `
    -ArgumentList "-m", "app.desktop.launch" `
    -WorkingDirectory $BackendDir `
    -PassThru `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog

$exitCode = 1
try {
    # CHECK 1-2: launcher starts and /health responds
    $health = $null
    for ($i = 1; $i -le 40; $i++) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8010/health" -TimeoutSec 2
            break
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    if ($null -eq $health) {
        Write-Host "FAIL: /health did not respond within 40s"
        Write-Host "--- launcher stdout ---"
        if (Test-Path $outLog) { Get-Content $outLog -Encoding UTF8 }
        Write-Host "--- launcher stderr ---"
        if (Test-Path $errLog) { Get-Content $errLog -Encoding UTF8 }
        exit 1
    }
    Write-Host "Health response:"
    $health | ConvertTo-Json -Depth 5

    # CHECK 3: app_edition
    if ($health.app_edition -ne "desktop_local") {
        Write-Host "FAIL: app_edition not desktop_local"
        exit 1
    }
    # CHECK 4: database_engine
    if ($health.database_engine -ne "sqlite") {
        Write-Host "FAIL: database_engine not sqlite"
        exit 1
    }

    # CHECK 5: bind local-only
    $listeners = Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue
    if (!$listeners) {
        Write-Host "FAIL: No listener on port 8010"
        exit 1
    }
    $badListeners = $listeners | Where-Object {
        $_.LocalAddress -ne "127.0.0.1" -and $_.LocalAddress -ne "::1"
    }
    if ($badListeners) {
        Write-Host "FAIL: Launcher is listening on non-local address"
        $badListeners | Format-Table -AutoSize
        exit 1
    }

    # CHECK 6: SQLite DB file created and API can read it
    $dbFile = Join-Path $RootDir "data\seamlessfordmis.db"
    if (Test-Path $dbFile) {
        Write-Host "PASS: SQLite DB exists at data\seamlessfordmis.db"
    } else {
        Write-Host "WARN: DB file not found at expected path: $dbFile"
    }
    try {
        $status = Invoke-RestMethod -Uri "http://127.0.0.1:8010/api/system/status" -TimeoutSec 10
        if ($null -ne $status.row_counts) {
            Write-Host "PASS: API reads SQLite (system status returned row_counts)"
        } else {
            Write-Host "WARN: system status returned but row_counts missing"
        }
    } catch {
        Write-Host "WARN: system status call failed: $($_.Exception.Message)"
    }

    # CHECK 7: launcher log readable + no obvious CID-like leak (13 consecutive digits)
    if (Test-Path $outLog) {
        Write-Host "--- launcher stdout (first 20 lines) ---"
        Get-Content $outLog -Encoding UTF8 -TotalCount 20
        $leak = Select-String -Path $outLog, $errLog -Pattern "\d{13}" -ErrorAction SilentlyContinue
        if ($leak) {
            Write-Host "WARN: 13-digit number found in launcher logs - review for identifier leak"
        } else {
            Write-Host "PASS: no 13-digit identifiers in launcher logs"
        }
    }

    Write-Host "PASS: launcher health OK"
    Write-Host "PASS: app_edition=desktop_local"
    Write-Host "PASS: database_engine=sqlite"
    Write-Host "PASS: bind is local-only (127.0.0.1)"
    Write-Host "PASS: no Docker used by this check"
    $exitCode = 0
} finally {
    # CHECK 8: shutdown
    if ($proc -and (-not $proc.HasExited)) {
        Write-Host "Stopping launcher process (PID $($proc.Id))..."
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    $still = Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue
    if ($still) {
        Write-Host "WARN: port 8010 still LISTENING after stop - check stray process with: netstat -ano | findstr :8010"
    } else {
        Write-Host "PASS: port 8010 released after shutdown"
    }
}

if ($exitCode -eq 0) {
    Write-Host ""
    Write-Host "D3.1 Windows launcher validation PASSED"
} else {
    Write-Host ""
    Write-Host "D3.1 Windows launcher validation FAILED - copy output above back to Claude"
}
exit $exitCode
