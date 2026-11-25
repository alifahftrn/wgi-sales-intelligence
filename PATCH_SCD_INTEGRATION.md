# SCD Type 2 integration test
- Dedicated local database `sales_datamart_scd_test`. Create it manually in pgAdmin. Do not point `.env` at it.
- Run `database/postgresql/03_SCD_Test_Foundation.sql` once in its Query Tool. It is the original foundation DDL with the database guard changed to the test DB. No fact tables are needed.
- `python -m unittest discover -v` (88 expected), `python manage.py check`, `python manage.py verify_scd_integration`.
- Test command uses explicit local connection to test DB and refuses nonempty test tables. Seven scenarios use the same execute implementation as the main loader, but not raw extraction or prepare. A database integrity error exercises savepoint rollback; an outer rollback removes all test rows (identity sequences may advance). Calendar remains intact. No production database writes.
- One file replaces existing `etl/load/dimensions.py`, adding a keyword-only test database guard. Default main behavior unchanged. Commit only patch files, not `.env` or `.local`.
- Unit tests executed on reconstructed project; real PostgreSQL integration must be run locally. No automatic DB creation or deletion.
