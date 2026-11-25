# Canonical Mapping V2 — MySQL full

Install over the project root after Mapping V1. Five new files only; no existing code or database changes. Python dependencies unchanged.

```
python -m unittest discover -v
python manage.py check
python manage.py map_sales_full --run-id 20261125T011526Z_fe5b47a2
```

Use the specified successful raw MySQL run or another full extract from the migrated 14-table schema. All 13 allowed datasets, including empty ones, and all 20 added columns must appear in the raw manifest. No credentials or author IDs. The raw and V1 output remain untouched. Output `.local/canonical_v2/mysql/<run-id>/` contains 13 JSONL files, manifest and quarantine. Existing V2 output is not overwritten; extract a fresh run to repeat.

Field names/types are declared in `etl/configurations/mysql_mapping_v2.yaml`. Identifiers are strings, packs are signed PostgreSQL-compatible nonnegative integers (PO/DO positive), decimal amounts are exact strings, absent optional values remain null. `updated_at` is interpreted as UTC because the MySQL adapter sets the session timezone to UTC. Legacy source DATETIME values are preserved without timezone; Transform must apply the agreed business timezone after verification. Snapshot observation time is copied from the extract manifest.

`READY` and `SUCCESS` describe row-level mapping, not readiness for fact loading. The manifest marks `load_ready: false`. Foreign key joins, grain duplication, status validity, historical snapshot completeness, price/PPN consistency, chronological validation, forecast selection, overdelivery, and KPI calculation are deferred to Transform. Partial mapping output must not be loaded as a full snapshot. Empty transaction data is not evidence that transaction logic works. Excel still uses V1 `map_sales`; complex company workbooks remain out of scope.

Tests run on reconstructed starter + previous patches with simulated rows, not the user's live databases. CLI and database integration must be checked locally.
