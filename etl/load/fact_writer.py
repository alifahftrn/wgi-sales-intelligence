"""Full-snapshot fact writer. Caller owns one transaction; no source deletes."""
from datetime import date, datetime
from decimal import Decimal
from etl.load.fact_planner import (TABLES, PKS, ORDER_FIELDS, HISTORY_FIELDS,
                                   MONTH_FIELDS, SNAP_FIELDS, inspect, report)

PREFIX = 'FACT_V1:'
ORDER, HISTORY, MONTH, SNAP = TABLES
FIELDS = {ORDER: (*ORDER_FIELDS, *PKS), HISTORY: (*HISTORY_FIELDS, *PKS),
          MONTH: (*MONTH_FIELDS, *PKS, 'cutoff_at'), SNAP: (*SNAP_FIELDS, *PKS)}
ORDER_KEY = ('jenis_record', 'id_detail_sumber')
HISTORY_KEY = ('jenis_forecast', 'id_detail_sumber')
ASP_KEY = ('bulan', 'kode_produk', 'kode_distributor', 'jenis_metrik')
ASP_FIELDS = (*ASP_KEY, 'id_asp_detail_sumber', 'waktu_penetapan_asp', 'qty_pack', 'total_liter', 'total_rupiah')
DATE_FIELDS = {'tanggal_po', 'tanggal_transaksi', 'tanggal_snapshot', 'bulan'}
TIME_FIELDS = {'source_updated_at', 'waktu_penetapan', 'waktu_penetapan_asp', 'cutoff_at'}
NUM_FIELDS = {'liter_per_pack','harga_dasar_pack','tarif_ppn','harga_pack_setelah_ppn','total_liter','total_rupiah'}


def typed(k,v):
    if v is None: return None
    if k in DATE_FIELDS: return date.fromisoformat(v) if isinstance(v,str) else v
    if k in TIME_FIELDS: return datetime.fromisoformat(v) if isinstance(v,str) else v
    if k in NUM_FIELDS: return Decimal(v)
    return v


def values(row, fields):
    return tuple(typed(k,row[k]) for k in fields)


def keyed(rows, fields):
    result = {values(r,fields):r for r in rows}
    if len(result) != len(rows): raise ValueError('identitas fact duplikat')
    return result


def transitions(plan, old_order, old_history, old_asp):
    """Reject disappearance and immutable plan edits before any DML."""
    new_o=keyed(plan[ORDER],ORDER_KEY); old_o=keyed(old_order,ORDER_KEY)
    new_h=keyed(plan[HISTORY],HISTORY_KEY); old_h=keyed(old_history,HISTORY_KEY)
    new_a=keyed([r for r in plan[MONTH] if r['jenis_metrik'].startswith('ASP_')],ASP_KEY)
    old_a=keyed(old_asp,ASP_KEY)
    for name,old,new in [('order',old_o,new_o),('forecast',old_h,new_h),('ASP',old_a,new_a)]:
        if set(old)-set(new): raise ValueError(f'{name}: identitas lama hilang; full snapshot perlu review')
    for key,row in old_h.items():
        if values(row,FIELDS[HISTORY])!=values(new_h[key],FIELDS[HISTORY]):
            raise ValueError('forecast immutable berubah; buat revisi baru atau review histori')
    for key,row in old_a.items():
        if values(row,ASP_FIELDS)!=values(new_a[key],ASP_FIELDS): raise ValueError('ASP immutable berubah; perlu review')
    order_changes=[r for k,r in new_o.items() if k not in old_o or values(r,FIELDS[ORDER])!=values(old_o[k],FIELDS[ORDER])]
    for r in order_changes:
        prior=old_o.get(values(r,ORDER_KEY))
        if prior and prior['source_updated_at'] and r['source_updated_at'] and typed('source_updated_at',r['source_updated_at'])<typed('source_updated_at',prior['source_updated_at']):
            raise ValueError('source_updated_at transaksi mundur')
    return order_changes,[r for k,r in new_h.items() if k not in old_h]


def select_rows(c,table,fields,where=''):
    c.execute(f'SELECT {", ".join(fields)} FROM public.{table} WHERE source_system=%s'+where,('MYSQL',))
    return [dict(zip(fields,r)) for r in c.fetchall()]


def insert(c,table,columns,params,suffix=''):
    c.execute(f'INSERT INTO public.{table} ({", ".join(columns)}) VALUES ({", ".join(["%s"]*len(columns))})'+suffix,params)


def reconcile(c,plan,summary,cutoff):
    for t in (ORDER,HISTORY,MONTH):
        c.execute(f'SELECT count(*) FROM public.{t} WHERE source_system=%s',('MYSQL',))
        if c.fetchone()[0]!=len(plan[t]): raise ValueError(f'rekonsiliasi jumlah {t} gagal')
    c.execute('SELECT count(*), coalesce(sum(qty_outstanding_bod),0), coalesce(sum(qty_outstanding_eligible),0) FROM public.fact_outstanding_snapshot WHERE source_system=%s AND cutoff_at=%s',('MYSQL',cutoff))
    if tuple(c.fetchone())!=(len(plan[SNAP]),summary['outstanding_bod_pack'],summary['outstanding_eligible_pack']): raise ValueError('rekonsiliasi outstanding gagal')
    expected=tuple(Decimal(summary[k]) for k in ('actual_pack','actual_liter','actual_rupiah'))
    for t,predicate in [(ORDER,"jenis_record='DO' AND valid_analitik"),(MONTH,"jenis_metrik='ACTUAL'")]:
        c.execute(f'SELECT coalesce(sum(qty_pack),0),coalesce(sum(total_liter),0),coalesce(sum(total_rupiah),0) FROM public.{t} WHERE source_system=%s AND {predicate}',('MYSQL',))
        if tuple(c.fetchone())!=expected: raise ValueError(f'rekonsiliasi actual {t} gagal')


def execute(c,p,apply=False,*,test_only=False):
    expected='sales_datamart_scd_test' if test_only else 'sales_datamart'
    c.execute('SELECT current_database()')
    if c.fetchone()[0]!=expected: raise ValueError(f'database tujuan bukan {expected}')
    c.execute("SET LOCAL lock_timeout = '5s'")
    c.execute('LOCK TABLE public.dim_produk, public.dim_distributor, public.etl_log, '+', '.join('public.'+t for t in TABLES)+' IN SHARE ROW EXCLUSIVE MODE')
    c.execute('LOCK TABLE public.dim_tanggal IN SHARE MODE')
    cutoff=p['cutoff']; key=PREFIX+p['run_id']; ref=f'canonical_v2/mysql/{p["run_id"]}#sha256={p["digest"]}'
    c.execute('SELECT status, extract_ref, cutoff_at FROM public.etl_log WHERE run_key=%s',(key,))
    prior=c.fetchone()
    if prior:
        if prior!=('SUCCESS',ref,cutoff): raise ValueError('identitas run fact berbeda')
        return dict(status='ALREADY_APPLIED',rows_written=0,cache_rows_removed=0)
    c.execute("SELECT max(cutoff_at) FROM public.etl_log WHERE source_system=%s AND run_key LIKE %s AND status='SUCCESS'",('MYSQL',PREFIX+'%'))
    latest=c.fetchone()[0]
    if latest is not None and cutoff<=latest: raise ValueError('cutoff fact tidak lebih baru')
    plan,summary,existing=inspect(c,p,test_only=test_only)
    old_order=select_rows(c,ORDER,FIELDS[ORDER]); old_history=select_rows(c,HISTORY,FIELDS[HISTORY]); old_asp=select_rows(c,MONTH,ASP_FIELDS," AND jenis_metrik IN ('ASP_INTERNAL','ASP_EXTERNAL')")
    orders,history=transitions(plan,old_order,old_history,old_asp)
    if latest is None and any(existing.values()): raise ValueError('fact sudah berisi data tanpa log loader; perlu review')
    c.execute('SELECT count(*) FROM public.fact_outstanding_snapshot WHERE source_system=%s AND cutoff_at=%s',('MYSQL',cutoff))
    if c.fetchone()[0]: raise ValueError('snapshot cutoff sudah ada tanpa log')
    writes=len(orders)+len(history)+len(plan[MONTH])+len(plan[SNAP]); result=report(plan,summary,existing)
    result.update(status='DRY_RUN',rows_written=0,cache_rows_removed=0,planned_writes=writes,planned_cache_removals=existing[MONTH])
    if not apply: return result
    c.execute("INSERT INTO public.etl_log (source_system,run_key,extract_ref,cutoff_at,trigger,status,rows_read,rows_written,rows_quarantine) VALUES (%s,%s,%s,%s,'MANUAL','RUNNING',%s,0,0) RETURNING id_run",('MYSQL',key,ref,cutoff,sum(len(v) for v in p['data'].values())))
    run=c.fetchone()[0]
    cols=(*FIELDS[ORDER],'id_run'); updates=[k for k in cols if k not in ('source_system',*ORDER_KEY)]
    for r in orders:
        insert(c,ORDER,cols,(*values(r,FIELDS[ORDER]),run),' ON CONFLICT (source_system, jenis_record, id_detail_sumber) DO UPDATE SET '+', '.join(f'{k}=EXCLUDED.{k}' for k in updates))
    for r in history:
        insert(c,HISTORY,(*FIELDS[HISTORY],'teramati_at','id_run'),(*values(r,FIELDS[HISTORY]),cutoff,run))
    lookup=keyed(select_rows(c,HISTORY,(*HISTORY_KEY,'id_forecast_history')),HISTORY_KEY)
    # Only the derived monthly cache is replaced, atomically and scoped to MYSQL.
    # The schema has no dependent FK on its surrogate key; no source/history deletes.
    c.execute('DELETE FROM public.fact_sales_monthly WHERE source_system=%s',('MYSQL',)); removed=c.rowcount
    if removed!=existing[MONTH]: raise ValueError('jumlah cache berubah')
    for r in plan[MONTH]:
        link=r['forecast_ref']; fid=lookup[tuple(link)]['id_forecast_history'] if link is not None else None
        insert(c,MONTH,(*FIELDS[MONTH],'id_forecast_history','id_run'),(*values(r,FIELDS[MONTH]),fid,run))
    for r in plan[SNAP]:
        insert(c,SNAP,(*FIELDS[SNAP],'id_run'),(*values(r,FIELDS[SNAP]),run))
    reconcile(c,plan,summary,cutoff)
    c.execute("UPDATE public.etl_log SET status='SUCCESS', selesai_at=clock_timestamp(), rows_written=%s WHERE id_run=%s AND status='RUNNING'",(writes,run))
    if c.rowcount!=1: raise ValueError('log fact gagal')
    result.update(status='FACTS_APPLIED',rows_written=writes,cache_rows_removed=removed)
    return result
