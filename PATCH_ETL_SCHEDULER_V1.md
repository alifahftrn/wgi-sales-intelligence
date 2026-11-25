# ETL Scheduler V1 (Windows development)

Requires the existing `run_etl` command from Pipeline V1. No change to Django, SQL, or dependencies. The script defaults to preview; `-Apply` explicitly enables a fresh full MySQL ETL into the configured Data Mart. Verify `.env` points to local development before enabling the scheduled task. Do not commit `.env`, `.local`, or logs.

Run from project root in PowerShell:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File .\scripts\run_etl_scheduled.ps1
$LASTEXITCODE
```

Then inspect `.local\scheduler_logs` (one status, stdout, stderr per invocation). Exit code 0 indicates that the child command exited successfully; check stdout for `ETL_PREVIEW_ONLY`, `ETL_APPLIED`, or `ETL_ALREADY_APPLIED` as appropriate. A success does not verify source coverage. Nonzero exit or a START without completion requires investigation; a hard stop can leave the pipeline lock. Never delete the lock while a pipeline is running. No automatic retry; verify etl_log before retrying an uncertain commit. The script does not delete old logs or raw snapshots.

After reviewing preview and confirming the local database, run with `-Apply` manually, inspect logs, then configure Task Scheduler daily at 00:00 using Windows time zone UTC+07:00 Bangkok/Hanoi/Jakarta. Run as the same Windows account used for development. Set multiple instances to Do not start a new instance. Do not enable forced timeout or automatic retry initially. MySQL and PostgreSQL must be running and accessible at execution time. For a laptop, jobs only run when the system/account conditions allow; enable missed-run execution if desired. For production migrate scheduling to an always-on server, with appropriate credentials and monitoring.

No Windows PowerShell runtime was available in the patch creation environment: test on the actual laptop before enabling automation.
