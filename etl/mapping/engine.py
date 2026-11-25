"""Read an explicit successful Extract run; publish canonical products atomically."""
import hashlib
import json
import re
import tempfile
import shutil
from decimal import Decimal
from pathlib import Path
import yaml
from .product import FIELDS, CORE, MappingError, map_product

RUN_ID = re.compile(r'\d{8}T\d{6}Z_[0-9a-f]{8}')

def map_run(raw_root, canonical_root, source, run_id, config_path=None):
    if source not in ('mysql','excel') or not RUN_ID.fullmatch(run_id):
        raise MappingError('source/run-id tidak valid')
    config_path = Path(config_path or Path(__file__).resolve().parents[1] / 'configurations' / 'product_mapping.yaml')
    config_bytes = config_path.read_bytes()
    config = yaml.safe_load(config_bytes)
    profile = config['profiles'][source]
    if (config['version'] != 1 or profile['source_system'] != source.upper()
            or not CORE <= set(profile['fields']) <= set(FIELDS)
            or len(set(profile['fields'].values())) != len(profile['fields'])):
        raise MappingError('profil mapping tidak valid')
    raw = Path(raw_root) / run_id
    manifest_bytes = (raw / 'manifest.json').read_bytes()
    m = json.loads(manifest_bytes)
    if m.get('status') != 'SUCCESS' or m.get('run_id') != run_id or m.get('source_type') != source:
        raise MappingError('manifest Extract tidak sesuai')
    tables = m['tables']
    matches = [t for t in tables if t['table'] == 'produk']
    if len(matches) != 1 or matches[0]['file'] != 'produk.jsonl':
        raise MappingError('dataset produk tidak tersedia atau ambigu')
    dataset = matches[0]
    columns = dataset['columns']
    if len(columns) != len(set(columns)) or not set(profile['fields'].values()) <= set(columns):
        raise MappingError('kolom sumber tidak sesuai profil mapping')
    root = Path(canonical_root) / source
    root.mkdir(parents=True, exist_ok=True)
    final = root / run_id
    if final.exists():
        raise MappingError('hasil mapping run ini sudah ada; gunakan run Extract baru')
    temp = Path(tempfile.mkdtemp(prefix='.partial-', dir=root))
    digest = hashlib.sha256()
    counts = {'rows_read':0, 'ready':0, 'incomplete':0, 'quarantine':0}
    seen = set()
    try:
        with (raw/'produk.jsonl').open('rb') as inp, (temp/'produk.jsonl').open('w', encoding='utf-8', newline='\n') as out, (temp/'quarantine.jsonl').open('w', encoding='utf-8', newline='\n') as bad:
            for n, line in enumerate(inp, 1):
                digest.update(line)
                counts['rows_read'] += 1
                row = json.loads(line, parse_float=Decimal)
                if not isinstance(row, dict) or set(row) != set(columns):
                    raise MappingError(f'baris {n}: struktur JSONL tidak sesuai manifest')
                try:
                    product = map_product(row, profile)
                except MappingError as exc:
                    counts['quarantine'] += 1
                    bad.write(json.dumps({'line':n,'reason':str(exc)}, ensure_ascii=False)+'\n')
                    continue
                key = product['kode_produk']
                if key in seen:
                    raise MappingError('kode produk canonical duplikat; tidak menerbitkan hasil ambigu')
                seen.add(key)
                counts[product['mapping_status'].lower()] += 1
                out.write(json.dumps(product, ensure_ascii=False, allow_nan=False)+'\n')
        if counts['rows_read'] != dataset['rows'] or digest.hexdigest() != dataset['sha256']:
            raise MappingError('checksum atau jumlah baris sumber tidak cocok')
        result = {'status':'PARTIAL' if counts['quarantine'] or counts['incomplete'] else 'SUCCESS',
                  'scope':'PRODUCT_ONLY', 'mapping_version':1, 'source_type':source,
                  'source_system':profile['source_system'], 'extract_run_id':run_id,
                  'extract_manifest_sha256':hashlib.sha256(manifest_bytes).hexdigest(),
                  'config_sha256':hashlib.sha256(config_bytes).hexdigest(),
                  'source_product_sha256':digest.hexdigest(), 'output_files':{},
                  'unmapped_datasets':[t['table'] for t in tables if t['table'] != 'produk'], **counts}
        for name in ('produk.jsonl','quarantine.jsonl'):
            result['output_files'][name] = hashlib.sha256((temp/name).read_bytes()).hexdigest()
        (temp/'manifest.json').write_text(json.dumps(result, indent=2, ensure_ascii=False),encoding='utf-8')
        temp.rename(final)
        return result
    finally:
        if temp.exists():
            shutil.rmtree(temp)
