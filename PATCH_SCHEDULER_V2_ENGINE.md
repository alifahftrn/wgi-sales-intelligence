# Scheduler V2 — Phase 14.1 (development)

Baseline: WGI_Source_Manual_ETL.zip plus WGI_Patch_Manual_ETL_V1.zip; user reports commit 45a7f16. All four patch files are new. Do not overwrite existing files. No requirements changes or migrations. Do not share local secrets.

## Commands (project root, active venv)

- `python -m unittest discover -v` — expected 157 tests.
- `python manage.py check`
- `python manage.py test accounts.django_checks etl.manual_django_checks -v 2` — existing 14 Django checks.
- `python manage.py etl_scheduler status` — reads journal, default disabled, 00:00 WIB, PREVIEW, no file created.
- `python manage.py etl_scheduler tick` — executes only a due enabled slot; disabled by default, not a forced run.

Before enabling the new scheduler, disable the old `WGI Daily Sales ETL` Windows task and verify no ETL is running. Do not delete that task. Keep MySQL and PostgreSQL running. On a Windows machine whose local clock is WIB, choose a test time about two minutes ahead:

```powershell
$jam = (Get-Date).AddMinutes(2).ToString('HH:mm')
python manage.py etl_scheduler configure --time $jam --mode PREVIEW --enable
python manage.py etl_scheduler run
```

Scheduler prints SCHEDULER_RUNNING and state transitions. Use a second terminal for `python manage.py etl_scheduler status`. Expect SUCCESS with `ETL_PREVIEW_ONLY` and a run ID after the due time. A PREVIEW creates local staging but does not load business data. Check status before stopping; Ctrl+C only while idle. Disable after testing: `python manage.py etl_scheduler configure --time 00:00 --mode PREVIEW --disable`. If the new scheduler is stopped/disabled and no ETL is active, restore the old Windows task until the new scheduler is ready for cutover.

APPLY mode is supported but not part of first test. It requires `--confirm-apply` when enabled. Do not enable both schedules. A preview consumes the same local date's scheduled attempt: changing time/mode that day does not create another scheduled attempt. Manual ETL remains available through the existing UI.

## Behavior
- Separate foreground process, polls every 10 seconds, reloads persisted configuration on each tick. Can run without web server. Standard library; uses UTC+07:00 for current WIB (no daylight saving). Windows/Linux compatible by design, not yet tested on either user's host or Linux with real databases.
- Daily, one attempted slot per WIB calendar date even if time changes. Five-minute eligibility window, including across midnight. When busy, can try claiming until window closes. No backlog/catch-up after window; missed slots are not recorded. Does not automatically retry failed/uncertain attempts.
- SQLite operational journal `.local/scheduler_v2.sqlite3` (not business database), separate from manual journal. Atomic slot claim prevents duplicate scheduler attempts sharing this directory. Existing `.pipeline.lock` remains authoritative for run_etl; manual and scheduler admission checks are advisory. If a competing process wins lock, run may fail and the slot is consumed. No multi-host support.
- RUNNING surviving a crash blocks future scheduler attempts until operator verifies process stopped, checks PostgreSQL etl_log, inspects shared lock and runs `python manage.py etl_scheduler recover --slot YYYY-MM-DD --confirm-stopped`. Recovery marks INTERRUPTED; never removes locks or automatically retries. Failure/interrupt does not prove rollback. Never recover live jobs or delete a lock blindly.
- Status/history accessible through terminal only in this patch. No heartbeat, web configuration, UI, service manager/autostart, missed-slot alerts or distributed lock. Disabled schedule does not cancel ongoing ETL. Laptop off/sleep prevents execution. Do not use in production yet.

## Verification
157 unit tests passed (143 baseline + 14 scheduler tests), Python syntax checked. Django and database integration not exercised in authoring environment; verify locally. No business data or credentials packaged.
