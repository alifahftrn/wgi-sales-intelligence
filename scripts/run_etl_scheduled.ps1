# Windows PowerShell 5.1 / PowerShell 7. Preview by default.
[CmdletBinding()]
param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$mode = if ($Apply) { 'APPLY' } else { 'PREVIEW' }
$logRoot = Join-Path $root '.local\scheduler_logs'
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ') + '_' + [guid]::NewGuid().ToString('N').Substring(0,8)
$exitCode = 1
$meta = $null
try {
    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    $meta = Join-Path $logRoot "$stamp.status.txt"
    $out = Join-Path $logRoot "$stamp.stdout.log"
    $err = Join-Path $logRoot "$stamp.stderr.log"
    "START | mode=$mode | utc=$([DateTime]::UtcNow.ToString('o'))" | Set-Content -LiteralPath $meta -Encoding UTF8
    $python = Join-Path (Split-Path -Parent $root) '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        $python = Join-Path $root '.venv\Scripts\python.exe'
    }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Virtual environment Python tidak ditemukan.' }
    if (-not (Test-Path -LiteralPath (Join-Path $root 'manage.py') -PathType Leaf)) { throw 'manage.py tidak ditemukan.' }
    $arguments = @('manage.py', 'run_etl', '--source', 'mysql')
    if ($Apply) { $arguments += '--apply' }
    $p = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $root -RedirectStandardOutput $out -RedirectStandardError $err -NoNewWindow -Wait -PassThru
    $exitCode = $p.ExitCode
    $status = if ($exitCode -eq 0) { 'SUCCESS' } else { 'FAILED' }
    "$status | exit_code=$exitCode | utc=$([DateTime]::UtcNow.ToString('o'))" | Add-Content -LiteralPath $meta -Encoding UTF8
    Write-Output "$status | mode=$mode | exit_code=$exitCode | log=$meta"
} catch {
    $exitCode = 1
    if ($meta) {
        try { "FAILED | exit_code=1 | utc=$([DateTime]::UtcNow.ToString('o')) | $($_.Exception.Message)" | Add-Content -LiteralPath $meta -Encoding UTF8 } catch { }
    }
    [Console]::Error.WriteLine($_.Exception.Message)
}
exit $exitCode
