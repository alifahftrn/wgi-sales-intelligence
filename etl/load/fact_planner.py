"""Read-only fact planning; no INSERT/UPDATE/DELETE or production fixture writes."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, localcontext
import yaml
from etl.load.dimensions import SPECS, PREFIX, attrs, prepare, utc
from etl.transform.plan_engine import CONFIG, preview
from etl.transform.order_engine import WIB

TABLES=('fact_order_delivery','fact_forecast_history','fact_sales_monthly','fact_outstanding_snapshot')
KEYS=('kode_produk','kode_distributor')
PKS=('id_produk_versi','id_distributor_versi')
ORDER_FIELDS='source_system jenis_record id_detail_sumber id_po_detail_sumber id_po_sumber no_po id_do_sumber no_do tanggal_po tanggal_transaksi kode_produk kode_distributor status_sumber valid_analitik qty_pack qty_batal_pack id_harga_sumber liter_per_pack harga_dasar_pack tarif_ppn harga_pack_setelah_ppn alasan_outstanding keterangan_outstanding source_updated_at'.split()
HISTORY_FIELDS='source_system jenis_forecast id_detail_sumber id_forecast_sumber id_revisi_sumber bulan kode_produk kode_distributor minggu_ke waktu_penetapan qty_pack total_liter total_rupiah'.split()
SNAP_FIELDS='source_system cutoff_at tanggal_snapshot id_po_detail_sumber id_po_sumber no_po tanggal_po kode_produk kode_distributor status_po valid_analitik qty_po_pack qty_do_pack qty_batal_pack liter_per_pack harga_pack_setelah_ppn alasan_outstanding keterangan_outstanding'.split()
MONTH_FIELDS='source_system bulan kode_produk kode_distributor jenis_metrik qty_pack total_liter total_rupiah id_asp_detail_sumber waktu_penetapan_asp'.split()

def project(row, fields):
    return {k:row.get(k) for k in fields}


def index_history(rows,pk,code):
    out=defaultdict(list)
    for r in rows: out[r[code]].append(r)
    for versions in out.values():
        versions.sort(key=lambda r:r['berlaku_mulai'])
        for i,r in enumerate(versions):
            start,end=r['berlaku_mulai'],r['berlaku_sampai']
            if (end is not None and end<=start) or r['aktif'] != (end is None): raise ValueError('interval dimensi tidak valid')
            if i and (versions[i-1]['berlaku_sampai'] is None or versions[i-1]['berlaku_sampai']>start): raise ValueError('overlap dimensi')
    return out


def resolve(index, code, pk, start, end=None):
    # A date-only event gets a version only if the whole day is covered.
    # No backfill from current master; a boundary inside a day is ambiguous.
    if code not in index: raise ValueError('kode tidak ditemukan di dimensi')
    for r in index[code]:
        stop=r['berlaku_sampai']
        if r['berlaku_mulai']<=start and (stop is None or (stop>=end if end is not None else stop>start)):
            return r[pk]
    return None


def day_window(value):
    start=datetime.combine(date.fromisoformat(value),time.min,tzinfo=WIB)
    return start,start+timedelta(days=1)


def build_plan(data, cutoff, histories):
    v=preview(data,cutoff,cutoff,yaml.safe_load(CONFIG.read_text(encoding='utf-8')))
    indices=[index_history(histories[k],pk,code) for k,pk,code in zip(SPECS,PKS,KEYS)]
    def attach(r, start, end=None):
        r.update({pk:resolve(ix,r[code],pk,start,end) for ix,code,pk in zip(indices,KEYS,PKS)})
        return r
    result={k:[] for k in TABLES}
    po={r['id_po']:r for r in data['purchase_order']}; do={r['id_do']:r for r in data['delivery_order']}
    pd={r['id_po_detail']:r for r in data['purchase_order_detail']}; dd={r['id_do_detail']:r for r in data['delivery_order_detail']}
    for r in v['order_delivery']:
        dest=project(r,ORDER_FIELDS); p=po[r['id_po_sumber']]; line=pd[r['id_po_detail_sumber']]
        source_rows=[p,line]
        if r['jenis_record']=='PO':
            dest.update(alasan_outstanding=p['alasan_tidak_terkirim'],keterangan_outstanding=p['keterangan_outstanding'])
        else: source_rows.extend([do[r['id_do_sumber']],dd[r['id_detail_sumber']]])
        stamps=[utc(x['source_updated_at']) for x in source_rows if x.get('source_updated_at') is not None]
        dest['source_updated_at']=max(stamps).isoformat() if len(stamps)==len(source_rows) else None
        result[TABLES[0]].append(attach(dest,*day_window(r['tanggal_transaksi'])))
    lookup={}
    for r in v['forecast_history']:
        dest=attach(project(r,HISTORY_FIELDS),datetime.fromisoformat(r['waktu_penetapan']))
        # teramati_at/id_run/identity are assigned by the future write transaction.
        ref=(r['jenis_forecast'],r['id_detail_sumber']); lookup[ref]=dest
        result[TABLES[1]].append(dest)
    for r in v['outstanding_snapshot']:
        result[TABLES[3]].append(attach(project(r,SNAP_FIELDS),*day_window(r['tanggal_po'])))
    with localcontext() as ctx:
        ctx.prec=80
        groups={}
        for r in result[TABLES[0]]:
            if r['jenis_record']!='DO' or not r['valid_analitik']: continue
            key=(r['tanggal_transaksi'][:7]+'-01',*(r[k] for k in (*KEYS,*PKS)))
            if key not in groups:
                groups[key]=dict(source_system='MYSQL',bulan=key[0],**dict(zip((*KEYS,*PKS),key[1:])),jenis_metrik='ACTUAL',qty_pack=0,total_liter=Decimal(0),total_rupiah=Decimal(0),id_asp_detail_sumber=None,waktu_penetapan_asp=None,forecast_ref=None,cutoff_at=cutoff.isoformat())
            g=groups[key]; g['qty_pack']+=r['qty_pack']; g['total_liter']+=r['qty_pack']*Decimal(r['liter_per_pack']); g['total_rupiah']+=r['qty_pack']*Decimal(r['harga_pack_setelah_ppn'])
        result[TABLES[2]].extend(groups.values())
        for r in v['monthly_metrics']:
            if r['jenis_metrik']=='ACTUAL': continue
            dest=project(r,MONTH_FIELDS); dest['cutoff_at']=cutoff.isoformat(); dest['forecast_ref']=None
            if r['jenis_metrik']=='FORECAST_LATEST':
                ref=r['forecast_ref']; key=(ref['jenis_forecast'],ref['id_detail_sumber']); history=lookup[key]
                dest.update({pk:history[pk] for pk in PKS}); dest['forecast_ref']=key
            else: attach(dest,datetime.fromisoformat(r['waktu_penetapan_asp']))
            result[TABLES[2]].append(dest)
        # Independent comparison of version-aware actual against transform summary.
        actual=[r for r in result[TABLES[2]] if r['jenis_metrik']=='ACTUAL']
        totals=tuple(sum((Decimal(r[k]) for r in actual),Decimal(0)) for k in ('qty_pack','total_liter','total_rupiah'))
        expected=tuple(Decimal(v['summary'][k]) for k in ('actual_pack','actual_liter','actual_rupiah'))
        if totals!=expected: raise ValueError('rekonsiliasi actual gagal')
        for rows in result.values():
            for r in rows:
                for k,val in r.items():
                    if val is None: continue
                    if k.startswith('qty_') and (not isinstance(val,int) or not 0<=val<=2**63-1): raise ValueError('qty di luar BIGINT')
                    if k in ('total_liter','total_rupiah'):
                        n=Decimal(val); p,s=(32,3) if k=='total_liter' else (42,2)
                        if n<0 or n>=10**(p-s) or n!=n.quantize(Decimal(1).scaleb(-s)): raise ValueError('nilai fact melebihi precision SQL')
    return result,v['summary']


def check_calendar(plan,calendar):
    for rows in plan.values():
        for r in rows:
            for k in ('tanggal_po','tanggal_transaksi','tanggal_snapshot','bulan'):
                if k in r and date.fromisoformat(r[k]) not in calendar: raise ValueError('tanggal di luar dim_tanggal')


def inspect(cursor,p,*,test_only=False):
    cursor.execute('SELECT current_database()')
    expected = 'sales_datamart_scd_test' if test_only else 'sales_datamart'
    if cursor.fetchone()[0]!=expected: raise ValueError(f'database tujuan bukan {expected}')
    ref=f'canonical_v2/mysql/{p["run_id"]}#sha256={p["digest"]}'
    cursor.execute('SELECT status, extract_ref, cutoff_at FROM public.etl_log WHERE run_key=%s',(PREFIX+p['run_id'],))
    if cursor.fetchone()!=('PARTIAL',ref,p['cutoff']): raise ValueError('load dimensi untuk run ini belum cocok')
    cursor.execute("SELECT max(cutoff_at) FROM public.etl_log WHERE source_system='MYSQL' AND run_key LIKE %s AND status='PARTIAL'",(PREFIX+'%',))
    if cursor.fetchone()[0]!=p['cutoff']: raise ValueError('bukan snapshot dimensi terbaru')
    histories={}
    for kind,(table,pk,code,fields) in SPECS.items():
        columns=(pk,code,*fields,'berlaku_mulai','berlaku_sampai','aktif')
        cursor.execute(f'SELECT {", ".join(columns)} FROM public.{table} WHERE source_system=%s',('MYSQL',))
        histories[kind]=[dict(zip(columns,r)) for r in cursor.fetchall()]
        active={r[code]:attrs(r,fields) for r in histories[kind] if r['aktif']}
        if active!={r[code]:attrs(r,fields) for r in p['data'][kind]}: raise ValueError('dimensi aktif tidak sama dengan snapshot')
    plan,summary=build_plan(p['data'],p['cutoff'],histories)
    cursor.execute('SELECT tanggal FROM public.dim_tanggal'); check_calendar(plan,{r[0] for r in cursor.fetchall()})
    counts={}
    for t in TABLES:
        cursor.execute(f'SELECT count(*) FROM public.{t} WHERE source_system=%s',('MYSQL',))
        counts[t]=cursor.fetchone()[0]
    return plan,summary,counts


def report(plan,summary,existing=None):
    result={'counts':{t:len(rows) for t,rows in plan.items()},'unresolved_version_refs':sum(r[pk] is None for rows in plan.values() for r in rows for pk in PKS),'actual_pack':summary['actual_pack'],'actual_liter':summary['actual_liter'],'actual_rupiah':summary['actual_rupiah'],'existing':existing}
    return result
