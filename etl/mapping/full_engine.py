"""Canonical MySQL V2. Row validation only; business joins/quality gate belong to Transform."""
import hashlib
import json
import shutil
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import yaml
from etl.schema import BASE, OPTIONAL_COLUMNS
from .engine import RUN_ID
from .product import MappingError, code


def convert(value, field):
    if value is None:
        if field['nullable']:
            return None
        raise MappingError('nilai wajib NULL')
    kind = field['type']
    if kind == 'code':
        return code(value)
    if kind in ('integer', 'decimal'):
        if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
            raise MappingError('angka tidak valid')
        try:
            d = Decimal(value)
            if not d.is_finite():
                raise MappingError('angka tidak finite')
            if kind == 'integer':
                if not field['min'] <= d <= field['max'] or d != d.to_integral_value():
                    raise MappingError('integer di luar rentang atau pecahan')
                return int(d)
            if not 0 <= d < Decimal(10)**(field['precision']-field['scale']) or (field['positive'] and d == 0):
                raise MappingError('desimal di luar rentang')
            if 'max' in field and d > Decimal(field['max']):
                raise MappingError('desimal melebihi batas')
            q = d.quantize(Decimal(1).scaleb(-field['scale']))
            if q != d:
                raise MappingError('presisi melebihi schema; tidak dibulatkan')
            return format(q, 'f')
        except (InvalidOperation, ValueError) as exc:
            if isinstance(exc, MappingError):
                raise
            raise MappingError('angka tidak valid') from exc
    if not isinstance(value, str):
        raise MappingError('teks/tanggal harus string')
    if kind == 'text':
        value = value.strip()
        if len(value) > field['limit'] or (not value and not field['allow_empty']):
            raise MappingError('teks kosong atau terlalu panjang')
        return value
    if kind == 'enum':
        if value not in field['values']:
            raise MappingError('nilai di luar domain')
        return value
    try:
        if kind == 'date':
            if len(value) != 10:
                raise ValueError('date')
            return date.fromisoformat(value).isoformat()
        if kind in ('utc_timestamp', 'local_datetime'):
            if len(value) < 19:
                raise ValueError('datetime')
            d = datetime.fromisoformat(value)
            if d.tzinfo is not None:
                raise ValueError('timezone tidak sesuai kontrak MySQL')
            if kind == 'utc_timestamp':
                d = d.replace(tzinfo=timezone.utc)
            return d.isoformat()
    except ValueError as exc:
        raise MappingError('tanggal atau timestamp tidak valid') from exc
    raise MappingError('tipe mapping tidak dikenal')


def map_row(table, row, spec):
    out = {'source_system': 'MYSQL'}
    for source, field in spec['fields'].items():
        try:
            out[field['name']] = convert(row[source], field)
        except MappingError as exc:
            raise MappingError(f'{source}: {exc}') from exc
    if table == 'produk' and Decimal(out['kemasan_liter'])*out['isi_karton'] != Decimal(out['liter_per_karton']):
        raise MappingError('volume produk tidak konsisten')
    if table == 'purchase_order_detail' and out['qty_batal_pack'] is not None and out['qty_batal_pack'] > out['qty_pack']:
        raise MappingError('qty batal melebihi PO')
    # READY means syntactically mapped, not safe to load as fact.
    return {**out, 'mapping_status': 'READY'}


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def map_full_run(raw_root, canonical_root, run_id, config_path=None):
    if not RUN_ID.fullmatch(run_id):
        raise MappingError('run-id tidak valid')
    config_path = Path(config_path or Path(__file__).resolve().parents[1]/'configurations'/'mysql_mapping_v2.yaml')
    config_bytes = config_path.read_bytes()
    profile = yaml.safe_load(config_bytes)
    specs = profile['datasets']
    if profile['version'] != 2 or profile['source_system'] != 'MYSQL' or set(specs) != set(BASE):
        raise MappingError('profil V2 tidak sesuai')
    for table, cols in BASE.items():
        spec = specs[table]
        fields = spec['fields']
        names = [f['name'] for f in fields.values()]
        if set(fields) != set(cols + OPTIONAL_COLUMNS[table]) or spec['primary_key'] != cols[0] or len(names) != len(set(names)) or set(names)&{'source_system','mapping_status'}:
            raise MappingError(f'profil {table} tidak sesuai allowlist')
    raw = Path(raw_root)/run_id
    manifest_bytes = (raw/'manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    if (manifest.get('status'),manifest.get('source_type'),manifest.get('run_id')) != ('SUCCESS','mysql',run_id):
        raise MappingError('manifest Extract tidak sesuai')
    tables = manifest['tables']
    by_name = {d['table']:d for d in tables}
    if len(by_name)!=len(tables) or set(by_name)!=set(specs):
        raise MappingError('13 dataset MySQL wajib tersedia tepat sekali')
    for table, spec in specs.items():
        d = by_name[table]
        cols = d['columns']
        if d['file'] != table+'.jsonl' or len(cols)!=len(set(cols)) or set(cols)!=set(spec['fields']):
            raise MappingError(f'{table}: schema V2 tidak lengkap atau berbeda')
    root = Path(canonical_root)/'mysql'
    root.mkdir(parents=True, exist_ok=True)
    final = root/run_id
    if final.exists():
        raise MappingError('hasil V2 sudah ada; gunakan run Extract baru')
    temp = Path(tempfile.mkdtemp(prefix='.partial-',dir=root))
    result = {'status':'SUCCESS','scope':'MYSQL_FULL','mapping_version':2,'source_type':'mysql','source_system':'MYSQL','extract_run_id':run_id,'extract_manifest_sha256':hashlib.sha256(manifest_bytes).hexdigest(),'config_sha256':hashlib.sha256(config_bytes).hexdigest(),'tables':{},'output_files':{},'rows_read':0,'ready':0,'quarantine':0,'time_note':'source_updated_at UTC; DATETIME sumber dipertahankan tanpa zona sampai aturan Transform dikonfirmasi','load_ready':False}
    result['snapshot_observed_at_utc'] = manifest.get('snapshot_observed_at_utc')
    result['extract_started_at_utc'] = manifest.get('started_at_utc')
    result['extract_finished_at_utc'] = manifest.get('finished_at_utc')
    try:
        with (temp/'quarantine.jsonl').open('w',encoding='utf-8',newline='\n') as bad:
            for table, spec in specs.items():
                d = by_name[table]
                counts = {'rows_read':0,'ready':0,'quarantine':0}
                digest = hashlib.sha256()
                seen = set()
                with (raw/d['file']).open('rb') as inp, (temp/d['file']).open('w',encoding='utf-8',newline='\n') as out:
                    for n,line in enumerate(inp,1):
                        digest.update(line); counts['rows_read'] += 1
                        row = json.loads(line,parse_float=Decimal)
                        if not isinstance(row,dict) or set(row)!=set(d['columns']):
                            raise MappingError(f'{table}: struktur JSONL tidak cocok')
                        key = code(row[spec['primary_key']])
                        if key in seen:
                            raise MappingError(f'{table}: primary key canonical duplikat')
                        seen.add(key)
                        try:
                            mapped = map_row(table,row,spec)
                        except MappingError as exc:
                            counts['quarantine'] += 1
                            bad.write(json.dumps({'table':table,'line':n,'reason':str(exc)},ensure_ascii=False)+'\n')
                            continue
                        counts['ready'] += 1
                        out.write(json.dumps(mapped,ensure_ascii=False,allow_nan=False)+'\n')
                if digest.hexdigest()!=d['sha256'] or counts['rows_read']!=d['rows']:
                    raise MappingError(f'{table}: checksum atau jumlah baris tidak sesuai')
                result['tables'][table] = {**counts,'source_sha256':digest.hexdigest()}
                for k in counts:
                    result[k] += counts[k]
        if result['quarantine']:
            result['status']='PARTIAL'
        for name in [t+'.jsonl' for t in specs]+['quarantine.jsonl']:
            result['output_files'][name]=sha(temp/name)
        (temp/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.rename(final)
        return result
    finally:
        if temp.exists():
            shutil.rmtree(temp)
