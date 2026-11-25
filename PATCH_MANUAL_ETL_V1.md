# Manual ETL Trigger V1 — localhost development

Patch based on the committed source in WGI_Source_Manual_ETL.zip (Authentication V1).

## Install

1. Confirm `git status --short` is empty and work on `feature/etl-engine`. Stop Django runserver (Ctrl+C); do not install while ETL is running. Back up the working tree or commit other changes first.
2. Extract the ZIP into the folder containing `manage.py`. Replace only `config/urls.py`, `etl/monitoring_views.py`, and `templates/etl_monitor_v1.html` if they match the supplied source. All other patch files are new. If those three have changed since the source ZIP, merge the changes rather than overwriting them.
3. No dependency additions, migrations, or changes to MySQL/PostgreSQL schema. Keep `.env` private and use a new secret if exposed.
4. Run `python -m unittest discover -v` (143 expected); `python manage.py check`; `python manage.py test accounts.django_checks etl.manual_django_checks -v 2` (14 expected). The 143 standard tests passed in the patch build environment; Django tests were authored but not run there because Django is unavailable. Run those tests locally before starting the server.
5. `python manage.py runserver 127.0.0.1:8000`; log in as ADMIN and open `/etl/monitoring/`.

## Acceptance test (development databases only)

- Click Run Preview. Refresh until SUCCESS / ETL_PREVIEW_ONLY. A new extract/mapping may be written locally but preview does not write PostgreSQL mart data. For new dimensions, fact DB validation may be deferred until Apply as in the existing pipeline.
- Check job ID, admin ID, stage, run ID and completion status. While active, controls should be disabled; server returns 409 to competing submissions. Scheduler/CLI use the existing pipeline lock; if one starts during manual startup, the losing invocation fails safely instead of overlapping. They are not queued automatically.
- Only after preview succeeds and the data mart is a development database, check the Apply confirmation and click Run Apply. This takes a NEW source snapshot, not the previously previewed snapshot. Expect SUCCESS / ETL_APPLIED or ETL_ALREADY_APPLIED, and appropriate PostgreSQL `etl_log` rows. Empty source transactions may result in zero fact rows. Source coverage remains NOT_VERIFIED.
- Log out and confirm access to monitor is denied/redirected; use mock tests for SALES/BOD, GET, CSRF, duplicate mode and missing Apply confirmation. Do not deliberately start a competing live Apply to test locking.
- Review `git status --short`; confirm `.env` and `.local` are not tracked. Stage patch files only, inspect staged diff, commit and push after all checks.

## Design and limits

POST `/etl/manual/run/` is local ADMIN only, CSRF protected and validates mode and Apply confirmation. Journal admission uses a unique partial SQLite index to reserve at most one active manual job. It launches the fixed management command with `sys.executable` and no shell; no user-supplied executable or argument injection. The worker claims exactly one PENDING job and calls the existing `run_etl`, which owns `.pipeline.lock`, extract/transform and the PostgreSQL atomic load. The scheduler and original pipeline are unchanged. Local SQLite journal `.local/manual_etl.sqlite3` records actor ID, mode, timestamps, status, PID, safe stage/run/outcome fields. It is not a third business database; no application migrations. Only whitelisted metadata, not raw command errors, is stored or displayed. History shows 20 rows and always includes an active job; UI refresh is manual. Local journal is not a production tamper-proof audit log. No automatic retry, cancellation, queue, or recovery on crash; no distributed or multi-host locking. Windows subprocess lifecycle must be tested locally. Closing the terminal or OS shutdown may interrupt the job. Do not delete journal/lock blindly. A command failure or interrupted report may occur after data mart commit; always inspect `etl_log` before retry. Preview and Apply are independent runs, not an approval of an identical snapshot.

## Recovery (only if job stuck)

Do not recover while a worker could still start or be running. On Windows, inspect the job PID and command line using Task Manager or PowerShell locally, and check scheduler/CLI execution. Stop runserver to prevent new manual requests and temporarily disable scheduled starts if needed. Verify no manual worker or `run_etl` process remains, no pipeline is running, and review PostgreSQL `etl_log` for recorded Run ID. A stale `.pipeline.lock` requires separate operator inspection and cleanup only after confirming all pipeline processes stopped; this patch never deletes it. If the lock is absent and the worker is conclusively stopped, use:

`python manage.py recover_manual_etl --job-id <JOB_ID> --confirm-stopped`

The status becomes INTERRUPTED, not rolled back. Review data mart and the original run ID before retry; do not retry blindly. Re-enable scheduler after inspection. Pending jobs can also remain after worker initialization failure. No recovery is necessary for a completed job.

## Frontend handoff

`templates/etl_manual_panel_v1.html` is a functional prototype. Keep form POST, CSRF, mode values PREVIEW/APPLY and confirm_apply=yes during redesign. Keep role enforcement server-side. UI can later add HTMX status polling, but V1 uses Refresh.
