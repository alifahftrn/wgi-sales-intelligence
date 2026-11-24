# WGI — Patch Adapter V2 (Phase 3)

Apply to existing wgi_sales_extract directory, not to its parent. Stop Django first; keep backup. This archive only adds/replaces ETL source files, tests, requirements and this guide. No .env, .local, settings, templates or SQL changes.

PowerShell (from wgi_sales_extract):

1. Extract the downloaded patch ZIP into this directory with `Expand-Archive -LiteralPath 'PATH_TO_ZIP' -DestinationPath . -Force`.
2. `..\.venv\Scripts\python.exe -m pip install -r requirements.txt`
3. `..\.venv\Scripts\python.exe -m unittest discover -v`
4. `..\.venv\Scripts\python.exe manage.py check`
5. `..\.venv\Scripts\python.exe manage.py extract_sales --source mysql`
6. `..\.venv\Scripts\python.exe manage.py create_extract_demo`
7. `..\.venv\Scripts\python.exe manage.py extract_sales --source excel --file .local\demo\produk_demo.xlsx`

MySQL still reads the original allowlist with read-only consistent snapshot, keyset pagination and schema warnings. Old `extract_sales` remains a MySQL default. Existing local web monitor remains MySQL-only. Excel demo expects a sheet named Produk with exact headers Product Code, Product Name, Volume per Carton; it rejects formula/error cells. Demo contains 3 fictional records. Source-specific field names are retained: mapping to the canonical model belongs to Transform, not Extract. Excel stages in .local/extracts_excel; MySQL in .local/extracts. Each run publishes a manifest and checksums only after success. No data mart writes. Only MySQL and configured Excel supported; no Sage/API connection implemented. Run localhost only and avoid committing .env, .local or backup. Test results use simulated MySQL, not your actual server.
