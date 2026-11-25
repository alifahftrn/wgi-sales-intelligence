# WGI — Transformation Preview V1 (PO/DO)

Prerequisites: Extract schema 14 tables, Mapping V2, Data Quality V1.
Extract this ZIP into `wgi_sales_extract`. Six new files; no replacements.

```powershell
python -m unittest discover -v
python manage.py check
python manage.py transform_sales_preview --demo
python manage.py transform_sales_preview --run-id 20261125T011526Z_fe5b47a2
```

Demo generates a fresh synthetic run under `.local/quality_demo` and writes a
preview to `.local/transform_v1/demo/<run-id>/preview.json`. Normal run reads
canonical_v2/mysql/<run-id> and writes `.local/transform_v1/mysql/<run-id>/preview.json`.
No SQL execution, no writes to MySQL/PostgreSQL, no dependencies added.
Never commit `.local`. Existing preview cannot be overwritten; use a fresh Extract + Mapping run.

V1 policy: OPEN = some eligible balance, no confirmed delivery; PARTIAL = some
confirmed delivery and eligible balance; COMPLETED = fully shipped; CANCELLED =
remaining quantity fully cancelled (possibly after partial shipment). Fully
cancelled PO before shipment is excluded from valid PO. A remaining balance
cancelled after partial shipment remains in BOD outstanding; eligible balance
subtracts cancellations. Only CONFIRMED DO is actual. Unknown/null status,
status/quantity mismatch and unresolved quality issues block the preview.
These are project assumptions, to be confirmed with business owner before production.
The original `validate_sales` V1 is unchanged and may still show its old status warning;
this preview revalidates known statuses instead of blindly accepting warnings.
Other warnings (including missing ASP or transaction snapshots) block the preview.

Actual is grouped by DO date month and natural source/product/distributor keys.
Price follows PO snapshot; volume follows DO snapshot. No current-master fallback.
PO and DO detail records are separate. Snapshot date is observed ETL date WIB,
not a reconstruction of historical cancellation balances. Fulfillment summary
uses all valid PO lines in the supplied snapshot; 0 denominator -> null.

Expected synthetic summary: PO 370, confirmed DO 290, actual 2784.000 L,
Rp 32190000.00, BOD outstanding 80, operational outstanding 70, fulfillment
78.38%, 7 order rows, 3 monthly groups, 3 snapshots.
Real master-only run has zero transaction rows; that is not evidence of zero
company sales. No monthly zero rows invented. ASP/forecast, growth, SCD2 version
resolution, ID assignment, DB numeric bounds for derived totals and load not implemented.
All output is PREVIEW_ONLY and load_ready=false, not a direct PostgreSQL insert payload.
Registry/config V1 only supports the three registered stages in dependency order;
not an arbitrary transformation DSL. Runs in memory; large-volume scalability not tested.

50 unit tests passed in reconstructed project including 12 new tests. Django CLI
and live databases were not exercised in build environment (Django unavailable).
