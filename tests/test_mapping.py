import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from etl.mapping.engine import map_run
from etl.mapping.product import MappingError

RUN = '20261125T011526Z_fe5b47a2'
MYSQL = {'kodeProduk':1001,'kodeAPCLama':None,'namaProduk':'Demo','brand':'Demo','jenisProduk':'2W','segment':'Mid','kemasanProduk':'0.800','isiKarton':12,'volumeTotal':'9.600'}
EXCEL = {'Product Code':'000123','Product Name':'Demo','Volume per Carton':9.6}

class MappingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
    def prepare(self, source, rows):
        path = self.root/'raw'/RUN
        path.mkdir(parents=True)
        data = ''.join(json.dumps(r)+'\n' for r in rows).encode()
        (path/'produk.jsonl').write_bytes(data)
        (path/'manifest.json').write_text(json.dumps({'status':'SUCCESS','source_type':source,'run_id':RUN,'tables':[{'table':'produk','file':'produk.jsonl','columns':list(rows[0]),'rows':len(rows),'sha256':hashlib.sha256(data).hexdigest()}]}))
        return path
    def run_map(self, source):
        return map_run(self.root/'raw',self.root/'canonical',source,RUN)
    def output(self, source):
        return self.root/'canonical'/source/RUN
    def test_mysql_complete(self):
        self.prepare('mysql',[MYSQL])
        self.assertEqual(self.run_map('mysql')['ready'],1)
        row = json.loads((self.output('mysql')/'produk.jsonl').read_text())
        self.assertEqual((row['kode_produk'],row['liter_per_karton'],row['isi_karton']),('1001','9.600',12))
    def test_excel_incomplete_preserves_code(self):
        self.prepare('excel',[EXCEL])
        self.assertEqual(self.run_map('excel')['incomplete'],1)
        row = json.loads((self.output('excel')/'produk.jsonl').read_text())
        self.assertEqual(row['kode_produk'],'000123')
        self.assertIsNone(row['brand'])
        self.assertEqual(row['mapping_status'],'INCOMPLETE')
    def test_bad_volume_quarantined(self):
        self.prepare('mysql',[{**MYSQL,'volumeTotal':'9.700'}])
        self.assertEqual(self.run_map('mysql')['quarantine'],1)
    def test_bad_precision_quarantined(self):
        self.prepare('excel',[{**EXCEL,'Volume per Carton':9.6001}])
        self.assertEqual(self.run_map('excel')['quarantine'],1)
    def test_checksum_no_publish(self):
        path = self.prepare('mysql',[MYSQL])
        (path/'produk.jsonl').write_text(json.dumps({**MYSQL,'namaProduk':'Changed'})+'\n')
        with self.assertRaises(MappingError): self.run_map('mysql')
        self.assertFalse(self.output('mysql').exists())
    def test_duplicate_no_publish(self):
        self.prepare('mysql',[MYSQL,MYSQL])
        with self.assertRaises(MappingError): self.run_map('mysql')
        self.assertFalse(self.output('mysql').exists())
    def test_existing_output_not_overwritten(self):
        self.prepare('mysql',[MYSQL])
        self.run_map('mysql')
        with self.assertRaises(MappingError): self.run_map('mysql')
        self.assertTrue(self.output('mysql').exists())
