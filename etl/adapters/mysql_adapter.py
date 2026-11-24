"""MySQL read-only consistent snapshot, restricted to WGI allowlist."""
from contextlib import contextmanager
from .base import BaseAdapter, Dataset
from ..errors import ExtractError
from ..schema import BASE, OPTIONAL_COLUMNS, HISTORY

def q(name):
    # Only call with identifiers from our static allowlist.
    return "`" + name.replace("`", "``") + "`"

def discover(cursor):
    cursor.execute("SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()")
    engines = dict(cursor.fetchall())
    cursor.execute("SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE()")
    metadata = {}
    for table, col, datatype in cursor.fetchall():
        metadata.setdefault(table, {})[col] = datatype
    plan, warnings = {}, []
    for table, required in {**BASE, **HISTORY}.items():
        if table not in engines and table in HISTORY:
            warnings.append(f"Tabel histori belum ada: {table}")
            continue
        if table not in engines or str(engines[table]).lower() != "innodb":
            raise ExtractError(f"Tabel {table} tidak tersedia atau bukan InnoDB.")
        types = metadata.get(table, {})
        missing = [c for c in required if c not in types]
        if missing:
            raise ExtractError(f"Kolom wajib {table} tidak ditemukan: {', '.join(missing)}")
        optional = OPTIONAL_COLUMNS.get(table, [])
        columns = required + [c for c in optional if c in types and c not in required]
        absent = [c for c in optional if c not in types]
        if absent:
            warnings.append(f"Kolom V3 belum ada pada {table}: {', '.join(absent)}")
        plan[table] = (columns, {c: types[c] for c in columns})
    return plan, warnings

class MySQLAdapter(BaseAdapter):
    source_type = "mysql"
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def snapshot(self):
        with self.connection.cursor() as cursor:
            self.cursor = cursor
            cursor.execute("SET time_zone = '+00:00'")
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
            try:
                cursor.execute("SELECT DATABASE(), UTC_TIMESTAMP(6)")
                self.database, self.observed_at = cursor.fetchone()
                yield self
            finally:
                cursor.execute("ROLLBACK")
                self.cursor = None

    def datasets(self):
        plan, warnings = discover(self.cursor)
        return [Dataset(t, tuple(cols), {"mysql_types": types}) for t, (cols, types) in plan.items()], warnings

    def rows(self, dataset, batch_size):
        columns = dataset.columns
        pk = columns[0]
        select = "SELECT " + ", ".join(map(q, columns)) + " FROM " + q(dataset.name)
        last = None
        while True:
            where = "" if last is None else f" WHERE {q(pk)} > %s"
            params = [batch_size] if last is None else [last, batch_size]
            self.cursor.execute(select + where + f" ORDER BY {q(pk)} LIMIT %s", params)
            rows = self.cursor.fetchall()
            if not rows:
                break
            for row in rows:
                if row[0] is None or (last is not None and row[0] <= last):
                    raise ExtractError(f"Primary key {dataset.name} tidak valid/berurutan.")
                last = row[0]
                yield dict(zip(columns, row))
            if len(rows) < batch_size:
                break

    def metadata(self):
        return {"database": self.database, "snapshot_observed_at_utc": str(self.observed_at),
                "time_note": "TIMESTAMP session UTC; DATETIME/DATE preserved as stored; legacy DATETIME interpretation deferred to Transform.",
                "excluded": ["pengguna (credentials/account data)", "dibuatOleh (author identifiers)"]}
