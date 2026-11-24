import json
import tempfile
import unittest
from pathlib import Path
from openpyxl import Workbook
from etl.adapters.factory import create_adapter
from etl.engine.extract_engine import run_adapter, latest
from etl.errors import ExtractError
from tests.test_extractor import FakeConnection

class AdapterTests(unittest.TestCase):
    def fixture(self, path, *, bad_header=False, formula=False, empty=False):
        wb = Workbook()
        ws = wb.active
        ws.title = 'Produk'
        ws.append(['Wrong' if bad_header else 'Product Code', 'Product Name', 'Volume per Carton'])
        if not empty:
            ws.append(['D-001', 'Demo', '=2+2' if formula else 9.6])
            ws.append(['D-002', 'Demo 2', 12])
        wb.save(path)

    def test_same_engine_two_sources(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            file = base/'demo.xlsx'
            self.fixture(file)
            mysql = run_adapter(create_adapter('mysql', connection=FakeConnection()), base/'mysql', 2)
            excel = run_adapter(create_adapter('excel', file=file), base/'excel', 2)
            self.assertEqual(mysql['source_type'], 'mysql')
            self.assertEqual(excel['source_type'], 'excel')
            self.assertEqual(excel['total_rows'], 2)
            self.assertEqual(mysql['total_rows'], 15)
            rows = (base/'excel'/excel['run_id']/'produk.jsonl').read_text().splitlines()
            self.assertEqual(json.loads(rows[0]), {'Product Code':'D-001','Product Name':'Demo','Volume per Carton':9.6})
            self.assertEqual(latest(base/'mysql')['run_id'], mysql['run_id'])
            self.assertEqual(len(excel['source_sha256']),64)

    def test_reject_wrong_header_and_formula(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            file=base/'demo.xlsx'
            for kwargs in ({'bad_header':True},{'formula':True}):
                self.fixture(file, **kwargs)
                with self.assertRaises(ExtractError):
                    run_adapter(create_adapter('excel',file=file), base/'stage')
                self.assertIsNone(latest(base/'stage'))
                self.assertEqual(list((base/'stage').iterdir()),[])

    def test_excel_empty(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            file=base/'demo.xlsx'
            self.fixture(file,empty=True)
            m=run_adapter(create_adapter('excel',file=file),base/'stage')
            self.assertEqual(m['total_rows'],0)
            self.assertEqual((base/'stage'/m['run_id']/'produk.jsonl').read_bytes(),b'')

    def test_factory_rejects_unknown(self):
        for source in ('sage','excel','mysql'):
            with self.assertRaises(ExtractError):
                create_adapter(source)
