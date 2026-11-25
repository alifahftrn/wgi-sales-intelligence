import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from etl.extractor import run, latest, ExtractError, ExtractBusy
from etl.schema import BASE, OPTIONAL_COLUMNS

class FakeCursor:
    def __init__(self, *, migrated=False, broken=False, fail=False):
        self.schema = {k:list(v) for k,v in BASE.items()}
        if migrated:
            for k,v in OPTIONAL_COLUMNS.items(): self.schema[k].extend(v)
        if broken: self.schema['produk'].remove('volumeTotal')
        self.fail = fail
        self.commands = []
        self.result = []
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def execute(self, sql, params=None):
        self.commands.append(sql)
        if sql.startswith('SELECT TABLE_NAME, ENGINE'):
            self.result = [(k,'InnoDB') for k in self.schema]
        elif sql.startswith('SELECT TABLE_NAME, COLUMN_NAME'):
            self.result = [(k,c,'decimal' if c=='volumeTotal' else 'int') for k,cols in self.schema.items() for c in cols]
        elif sql.startswith('SELECT DATABASE()'):
            self.result = [('salesdashboard',datetime(2026,11,24,0,0))]
        elif sql.startswith('SELECT `'):
            table = sql.split(' FROM `')[1].split('`')[0]
            if self.fail and table=='produk': raise RuntimeError('Simulated connection error')
            columns = [v.strip('`') for v in sql.split(' FROM ')[0][7:].split(', ')]
            ids = list(range(1,6)) if table in ('produk','distributor','harga_produk') else []
            if ' WHERE ' in sql: ids = [i for i in ids if i>params[0]]
            self.result = [tuple(i if j==0 else Decimal('9.600') if c=='volumeTotal' else None for j,c in enumerate(columns)) for i in ids[:params[-1]]]
        else: self.result = []
    def fetchall(self): return self.result
    def fetchone(self): return self.result[0]

class FakeConnection:
    def __init__(self, **kwargs): self.c = FakeCursor(**kwargs)
    def cursor(self): return self.c

class ExtractTests(unittest.TestCase):
    def test_baseline_15_rows_and_empty_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            conn = FakeConnection()
            m = run(conn, directory, 2)
            self.assertEqual(m['total_rows'],15)
            self.assertEqual(len(m['tables']),13)
            self.assertEqual(len(m['warnings']),13)
            self.assertTrue(all('Kolom skema 14 tabel' in w for w in m['warnings']))
            folder = Path(directory)/m['run_id']
            self.assertEqual((folder/'asp.jsonl').read_bytes(), b'')
            rows = [json.loads(s) for s in (folder/'produk.jsonl').read_text().splitlines()]
            self.assertEqual(rows[0]['volumeTotal'],'9.600')
            self.assertEqual([r['kodeProduk'] for r in rows], list(range(1,6)))
            self.assertEqual(latest(directory)['run_id'],m['run_id'])
            self.assertEqual(conn.c.commands[-1],'ROLLBACK')
            self.assertFalse(any('`pengguna`' in cmd for cmd in conn.c.commands))
            for table in m['tables']:
                self.assertEqual(hashlib.sha256((folder/table['file']).read_bytes()).hexdigest(),table['sha256'])
    def test_migrated_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            m=run(FakeConnection(migrated=True),directory,2)
            self.assertEqual(len(m['tables']),13)
            by_table = {t['table']:t for t in m['tables']}
            self.assertEqual(set(by_table), set(BASE))
            self.assertEqual(sum(map(len, OPTIONAL_COLUMNS.values())), 20)
            self.assertEqual(set(by_table['purchase_order_detail']['columns']), {
                'idPODetail', 'idPO', 'kodeProduk', 'idHarga', 'qtyPack',
                'updated_at', 'literPerPackSaatPO', 'hargaDasarPackSaatPO',
                'tarifPPNSaatPO', 'hargaPackSetelahPPN', 'qtyBatalPack'})
            self.assertIn('literPerPackSaatDO', by_table['delivery_order_detail']['columns'])
            self.assertIn('waktuPenetapan', by_table['asp_detail']['columns'])
            self.assertTrue(all('updated_at' in t['columns'] for t in m['tables']))
            self.assertFalse(any('idVersiProduk' in t['columns'] or 'idVersiDistributor' in t['columns'] for t in m['tables']))
            self.assertEqual(m['warnings'],[])
    def test_missing_new_column_warns(self):
        with tempfile.TemporaryDirectory() as directory:
            conn = FakeConnection(migrated=True)
            conn.c.schema['purchase_order_detail'].remove('qtyBatalPack')
            m = run(conn, directory, 2)
            self.assertEqual(len(m['tables']), 13)
            self.assertEqual(m['warnings'], ['Kolom skema 14 tabel belum ada pada purchase_order_detail: qtyBatalPack'])

    def test_extra_tables_and_columns_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            conn = FakeConnection(migrated=True)
            conn.c.schema['riwayat_master_produk'] = ['idVersiProduk']
            conn.c.schema['pengguna'] = ['idPengguna', 'password']
            conn.c.schema['asp_detail'].append('idVersiProduk')
            m = run(conn, directory, 2)
            self.assertEqual(len(m['tables']), 13)
            self.assertEqual(m['warnings'], [])
            self.assertFalse(any('idVersiProduk' in t['columns'] for t in m['tables']))
            self.assertFalse(any('`pengguna`' in cmd or '`riwayat_master_produk`' in cmd for cmd in conn.c.commands))

    def test_failure_does_not_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            good=run(FakeConnection(),directory,2)
            conn=FakeConnection(fail=True)
            with self.assertRaises(RuntimeError): run(conn,directory,2)
            self.assertEqual(latest(directory)['run_id'],good['run_id'])
            self.assertEqual(conn.c.commands[-1],'ROLLBACK')
            self.assertEqual(len(list(Path(directory).iterdir())),1)
    def test_missing_required_column(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ExtractError): run(FakeConnection(broken=True),directory)
            self.assertIsNone(latest(directory))
    def test_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'.extract.lock').mkdir()
            with self.assertRaises(ExtractBusy): run(FakeConnection(),directory)

if __name__=='__main__': unittest.main()
