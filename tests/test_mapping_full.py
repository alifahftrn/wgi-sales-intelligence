import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import yaml
from etl.mapping.full_engine import map_full_run, map_row, MappingError
from etl.schema import BASE, OPTIONAL_COLUMNS

RUN = '20261125T011526Z_fe5b47a2'
CONFIG = Path(__file__).resolve().parents[1]/'etl/configurations/mysql_mapping_v2.yaml'
SPECS = yaml.safe_load(CONFIG.read_text())['datasets']


def fixture(table):
    row = {}
    for name, f in SPECS[table]['fields'].items():
        kind = f['type']
        row[name] = {'code':1,'integer':1,'decimal':'1','text':'Demo','enum':(f.get('values') or [''])[0],'date':'2026-11-25','utc_timestamp':'2026-11-25T01:00:00','local_datetime':'2026-11-25T08:00:00'}[kind]
        if f['nullable']:
            row[name]=None
    return row

class FullMappingTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.raw = self.root/'raw'/RUN
        self.raw.mkdir(parents=True)
        self.output = self.root/'canonical'/'mysql'/RUN
    def prepare(self, overrides=None, only_master=False):
        tables = []
        for t in SPECS:
            rows = [fixture(t)] if not only_master or t in ('produk','distributor','harga_produk') else []
            if overrides and t in overrides: rows=overrides[t]
            data = ''.join(json.dumps(r)+'\n' for r in rows).encode()
            (self.raw/(t+'.jsonl')).write_bytes(data)
            tables.append({'table':t,'file':t+'.jsonl','columns':BASE[t]+OPTIONAL_COLUMNS[t],'rows':len(rows),'sha256':hashlib.sha256(data).hexdigest()})
        (self.raw/'manifest.json').write_text(json.dumps({'status':'SUCCESS','source_type':'mysql','run_id':RUN,'tables':tables}))
    def run_map(self):
        return map_full_run(self.root/'raw',self.root/'canonical',RUN)
    def test_full_all_13_with_rows(self):
        self.prepare(); m=self.run_map()
        self.assertEqual((m['status'],m['ready'],m['quarantine']),('SUCCESS',13,0))
        self.assertEqual(len(m['tables']),13)
        self.assertFalse(m['load_ready'])
        row=json.loads((self.output/'purchase_order_detail.jsonl').read_text())
        self.assertEqual(row['qty_pack'],1)
        self.assertEqual(row['id_po'],'1')
        self.assertIsNone(row['qty_batal_pack'])
        self.assertEqual(row['source_updated_at'],'2026-11-25T01:00:00+00:00')
    def test_empty_transactions(self):
        self.prepare(only_master=True); m=self.run_map()
        self.assertEqual(m['ready'],3)
        self.assertEqual((self.output/'asp.jsonl').read_bytes(),b'')
    def test_fractional_or_negative_packs(self):
        self.prepare({'purchase_order_detail':[{**fixture('purchase_order_detail'),'qtyPack':'1.2'},{**fixture('purchase_order_detail'),'idPODetail':2,'qtyPack':-1}]})
        m=self.run_map(); self.assertEqual((m['status'],m['quarantine']),('PARTIAL',2))
    def test_cancellation_over_order(self):
        self.prepare({'purchase_order_detail':[{**fixture('purchase_order_detail'),'qtyBatalPack':2}]})
        self.assertEqual(self.run_map()['quarantine'],1)
    def test_decimal_precision(self):
        self.prepare({'forecast_detail':[{**fixture('forecast_detail'),'forecastLiter':'0.0001'}]})
        self.assertEqual(self.run_map()['quarantine'],1)
    def test_checksum_no_publish(self):
        self.prepare(); (self.raw/'asp.jsonl').write_bytes(b'')
        with self.assertRaises(MappingError): self.run_map()
        self.assertFalse(self.output.exists())
    def test_missing_dataset_no_publish(self):
        self.prepare(); path=self.raw/'manifest.json'; m=json.loads(path.read_text());m['tables'].pop();path.write_text(json.dumps(m))
        with self.assertRaises(MappingError): self.run_map()
        self.assertFalse(self.output.exists())
    def test_duplicate_no_publish(self):
        self.prepare({'produk':[fixture('produk'),fixture('produk')]})
        with self.assertRaises(MappingError): self.run_map()
        self.assertFalse(self.output.exists())
    def test_existing_output_not_overwritten(self):
        self.prepare(); self.run_map()
        with self.assertRaises(MappingError): self.run_map()
        self.assertTrue(self.output.exists())
    def test_missing_required_nullable_column_manifest(self):
        self.prepare(); path=self.raw/'manifest.json';m=json.loads(path.read_text());m['tables'][0]['columns'].remove('updated_at');path.write_text(json.dumps(m))
        with self.assertRaises(MappingError): self.run_map()
        self.assertFalse(self.output.exists())
    def test_timestamp_and_domain(self):
        row=map_row('asp',fixture('asp'),SPECS['asp']);self.assertEqual(row['tanggal_input'],'2026-11-25T08:00:00')
        with self.assertRaises(MappingError): map_row('asp',{**fixture('asp'),'jenisTarget':'Unknown'},SPECS['asp'])
