"""MySQL canonical -> PostgreSQL dimensions. No fact loading in this phase."""
import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from etl.mapping.full_engine import sha
from etl.mapping.engine import RUN_ID
from etl.quality.validator import read_run, validate

SPECS = {
    'produk': ('dim_produk','id_produk_versi','kode_produk',('kode_apc_lama','nama_produk','brand','jenis_produk','segment','kemasan_liter','isi_karton','liter_per_karton')),
    'distributor': ('dim_distributor','id_distributor_versi','kode_distributor',('nama_distributor','area','region','wilayah')),
}
DECIMALS = {'kemasan_liter','liter_per_karton'}
PREFIX='DIM_V1:'


def utc(value):
    if isinstance(value,str): value=datetime.fromisoformat(value)
    if not isinstance(value,datetime): raise ValueError('timestamp tidak valid')
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def prepare(raw_root,canonical_root,run_id):
    if not RUN_ID.fullmatch(run_id): raise ValueError('run-id tidak valid')
    raw=Path(raw_root)/run_id/'manifest.json'
    canonical=Path(canonical_root)/'mysql'/run_id/'manifest.json'
    digest=sha(canonical); raw_digest=sha(raw)
    m=json.loads(canonical.read_text(encoding='utf-8')); r=json.loads(raw.read_text(encoding='utf-8'))
    if (r.get('run_id'),r.get('source_type'),r.get('status'),r.get('mode'),r.get('database')) != (run_id,'mysql','SUCCESS','FULL_EXTRACT','salesdashboard') or r.get('synthetic'):
        raise ValueError('hanya Extract MySQL salesdashboard asli; demo ditolak')
    if m.get('extract_manifest_sha256')!=raw_digest: raise ValueError('checksum manifest Extract berbeda')
    cutoff=utc(m['snapshot_observed_at_utc'])
    if cutoff!=utc(r['snapshot_observed_at_utc']) or cutoff>datetime.now(timezone.utc): raise ValueError('snapshot UTC tidak valid')
    data=read_run(canonical_root,run_id)
    if sha(canonical)!=digest or sha(raw)!=raw_digest: raise ValueError('manifest berubah')
    quality=validate(data)
    if quality['errors']: raise ValueError('Data Quality memiliki error; load dimensi ditolak')
    if not all(data[k] for k in SPECS): raise ValueError('master kosong; load ditolak')
    return {'run_id':run_id,'digest':digest,'cutoff':cutoff,'data':data,'warnings':quality['warnings']}


def attrs(row,fields):
    return tuple(Decimal(row[k]) if k in DECIMALS else row[k] for k in fields)


def plan_table(kind,incoming,existing,cutoff):
    _,pk,key,fields=SPECS[kind]
    groups=defaultdict(list)
    for row in existing: groups[row[key]].append(row)
    source={row[key]:row for row in incoming}
    if len(source)!=len(incoming): raise ValueError('duplikat kode canonical')
    if not source: raise ValueError('master kosong')
    if set(groups)-set(source): raise ValueError(f'{kind}: kode lama hilang dari full snapshot; periksa sumber, tidak otomatis menutup versi')
    changes=[]
    for code,row in source.items():
        history=sorted(groups.get(code,[]),key=lambda x:x['berlaku_mulai'])
        previous_end=None
        for i,h in enumerate(history):
            start=h['berlaku_mulai']; end=h['berlaku_sampai']
            if h['aktif']!=(end is None) or (end is not None and end<=start): raise ValueError('interval SCD2 tidak valid')
            if i and (previous_end is None or previous_end>start): raise ValueError('overlap interval SCD2')
            if start>cutoff or (end is not None and end>cutoff): raise ValueError('snapshot lebih lama dari histori')
            previous_end=end
        values=attrs(row,fields)
        if not history:
            changes.append(('insert',code,values,None)); continue
        active=history[-1]
        if not active['aktif']: raise ValueError('histori tanpa versi aktif; perlu pemeriksaan manual')
        if attrs(active,fields)==values:
            changes.append(('unchanged',code,values,None)); continue
        if cutoff<=active['berlaku_mulai']: raise ValueError('perubahan pada cutoff sama atau lebih lama')
        changes.append(('version',code,values,active[pk]))
    return changes


def execute(cursor,prepared,apply=False,*,test_only=False):
    """Caller must own a transaction on datamart; SQL identifiers are static."""
    cursor.execute('SELECT current_database()')
    expected = 'sales_datamart_scd_test' if test_only else 'sales_datamart'
    if cursor.fetchone()[0] != expected: raise ValueError(f'database tujuan bukan {expected}')
    # Serialize this loader and prevent concurrent modifications while planning.
    cursor.execute('SET LOCAL lock_timeout = \'5s\'')
    cursor.execute('LOCK TABLE public.dim_produk, public.dim_distributor, public.etl_log IN SHARE ROW EXCLUSIVE MODE')
    run=prepared['run_id']; cutoff=prepared['cutoff']; key=PREFIX+run
    ref=f'canonical_v2/mysql/{run}#sha256={prepared["digest"]}'
    cursor.execute('SELECT status, extract_ref, cutoff_at FROM public.etl_log WHERE run_key=%s',(key,))
    prior=cursor.fetchone()
    if prior:
        if prior!=('PARTIAL',ref,cutoff): raise ValueError('run_key sudah ada dengan identitas berbeda')
        return {'status':'ALREADY_APPLIED','tables':{},'rows_written':0}
    cursor.execute("SELECT max(cutoff_at) FROM public.etl_log WHERE source_system=%s AND run_key LIKE %s AND status='PARTIAL'",('MYSQL',PREFIX+'%'))
    latest=cursor.fetchone()[0]
    if latest is not None and cutoff<=latest: raise ValueError('snapshot tidak lebih baru dari load sebelumnya')
    plans={}; counts={}
    for kind,(table,pk,code,fields) in SPECS.items():
        columns=(pk,code,*fields,'berlaku_mulai','berlaku_sampai','aktif')
        cursor.execute(f'SELECT {", ".join(columns)} FROM public.{table} WHERE source_system=%s',('MYSQL',))
        existing=[dict(zip(columns,r)) for r in cursor.fetchall()]
        plans[kind]=plan_table(kind,prepared['data'][kind],existing,cutoff)
        counts[kind]={a:sum(x[0]==a for x in plans[kind]) for a in ('insert','version','unchanged')}
    written=sum(v['insert']+2*v['version'] for v in counts.values())
    if not apply: return {'status':'DRY_RUN','tables':counts,'rows_written':0,'planned_writes':written}
    # Atomically insert log and dimension changes. PARTIAL denotes dimension-only scope.
    cursor.execute("INSERT INTO public.etl_log (source_system,run_key,extract_ref,cutoff_at,trigger,status,rows_read,rows_written,rows_quarantine) VALUES (%s,%s,%s,%s,'MANUAL','RUNNING',%s,0,0)",('MYSQL',key,ref,cutoff,sum(len(prepared['data'][k]) for k in SPECS)))
    for kind,(table,pk,code,fields) in SPECS.items():
        columns=('source_system',code,*fields,'berlaku_mulai','aktif')
        for action,ident,values,old_pk in plans[kind]:
            if action=='unchanged': continue
            if action=='version':
                cursor.execute(f'UPDATE public.{table} SET berlaku_sampai=%s, aktif=false WHERE {pk}=%s AND aktif',(cutoff,old_pk))
                if cursor.rowcount!=1: raise ValueError('versi aktif berubah; rollback')
            params=('MYSQL',ident,*values,cutoff,True)
            cursor.execute(f'INSERT INTO public.{table} ({", ".join(columns)}) VALUES ({", ".join(["%s"]*len(params))})',params)
    cursor.execute("UPDATE public.etl_log SET status='PARTIAL', selesai_at=clock_timestamp(), rows_written=%s WHERE run_key=%s AND status='RUNNING'",(written,key))
    if cursor.rowcount!=1: raise ValueError('log tidak berhasil diperbarui')
    return {'status':'DIMENSIONS_APPLIED','tables':counts,'rows_written':written}
