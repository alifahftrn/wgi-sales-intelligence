"""Read-only plan and monthly KPI preview. No DB loading or historical reconstruction."""
import calendar
import json
import shutil
import tempfile
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, localcontext, ROUND_HALF_UP
from pathlib import Path

import yaml
from etl.mapping.engine import RUN_ID
from etl.mapping.full_engine import sha
from etl.quality.validator import read_run
from etl.transform.order_engine import CONFIG as ORDER_CONFIG, WIB, preview as order_preview

CONFIG = Path(__file__).resolve().parents[1] / 'configurations' / 'plan_transform_v2.yaml'
FIELDS = ('qty_pack', 'total_liter', 'total_rupiah')
METRICS = ('pack','liter','rupiah')

def business_time(value):
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is not None:
        raise ValueError('DATETIME bisnis MySQL harus tanpa zona; kontrak V2 WIB')
    return stamp.replace(tzinfo=WIB)


def key(r):
    return (r['source_system'],r['bulan'],r['kode_produk'],r['kode_distributor'])


def month(value):
    return value[:7]+'-01'


def month_key(k):
    return dict(zip(('source_system','bulan','kode_produk','kode_distributor'),k))


def values(r):
    return [Decimal(r[f]) for f in FIELDS] if r is not None else [None]*3


def pct(a,b):
    return None if a is None or b is None or b == 0 else str((a*100/b).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))


def plan_history(data, observed, cutoff):
    asp={r['id_asp']:r for r in data['asp']}
    fc={r['id_forecast']:r for r in data['forecast']}
    rev={r['id_revisi']:r for r in data['revisi_forecast']}
    plans=[]; history=[]
    def check_stamp(t):
        if t > observed: raise ValueError('waktu penetapan melebihi snapshot sumber; periksa zona waktu')
    for r in data['asp_detail']:
        h=asp[r['id_asp']]; t=business_time(r['waktu_penetapan']); check_stamp(t)
        if t < business_time(h['tanggal_input']): raise ValueError('ASP ditetapkan sebelum input header')
        if t <= cutoff:
            plans.append(dict(source_system='MYSQL',bulan=f"{h['tahun']:04d}-{r['bulan']:02d}-01",kode_produk=r['kode_produk'],kode_distributor=h['kode_distributor'],jenis_metrik='ASP_'+h['jenis_target'].upper(),qty_pack=r['target_pack'],total_liter=r['target_liter'],total_rupiah=r['target_rupiah'],id_asp_detail_sumber=r['id_asp_detail'],waktu_penetapan_asp=t.isoformat()))
    def append(r,h,revision=None):
        is_rev=revision is not None; prefix='revisi' if is_rev else 'forecast'
        t=business_time(revision['tanggal_revisi'] if is_rev else h['tanggal_input']); check_stamp(t)
        history.append(dict(source_system='MYSQL',bulan=month(h['bulan_forecast']),kode_produk=r['kode_produk'],kode_distributor=h['kode_distributor'],jenis_forecast='REVISI' if is_rev else 'BASELINE',id_detail_sumber=r['id_revisi_detail' if is_rev else 'id_forecast_detail'],id_forecast_sumber=h['id_forecast'],id_revisi_sumber=revision['id_revisi'] if is_rev else None,minggu_ke=revision['minggu_ke'] if is_rev else None,waktu_penetapan=t.isoformat(),qty_pack=r[prefix+'_pack'],total_liter=r[prefix+'_liter'],total_rupiah=r[prefix+'_rupiah']))
    for r in data['forecast_detail']: append(r,fc[r['id_forecast']])
    for r in data['revisi_forecast_detail']:
        h=rev[r['id_revisi']]; append(r,fc[h['id_forecast']],h)
    latest={}
    def rank(r): return (datetime.fromisoformat(r['waktu_penetapan']),r['jenis_forecast']=='REVISI',r['id_detail_sumber'])
    for r in history:
        if rank(r)[0] <= cutoff and (key(r) not in latest or rank(r)>rank(latest[key(r)])):
            latest[key(r)]=r
    for k,r in sorted(latest.items()):
        plans.append(dict(month_key(k),jenis_metrik='FORECAST_LATEST',qty_pack=r['qty_pack'],total_liter=r['total_liter'],total_rupiah=r['total_rupiah'],forecast_ref={x:r[x] for x in ('jenis_forecast','id_detail_sumber','id_forecast_sumber','id_revisi_sumber','waktu_penetapan')}))
    return plans,history


def monthly_metrics(rows, observed):
    groups=defaultdict(dict)
    for r in rows:
        g=groups[key(r)]; kind=r['jenis_metrik']
        if kind in g: raise ValueError('metrik bulanan duplikat')
        g[kind]=r
    output=[]; wape_parts=defaultdict(lambda: [Decimal(0),Decimal(0),0,0])
    for k,g in sorted(groups.items()):
        a=values(g.get('ACTUAL')); f=values(g.get('FORECAST_LATEST'))
        d=date.fromisoformat(k[1]); n=calendar.monthrange(d.year,d.month)[1]
        elapsed=0 if d>observed else observed.day if d.year==observed.year and d.month==observed.month else n
        r=dict(month_key(k),actual_present='ACTUAL' in g,days_elapsed=elapsed,days_in_month=n,partial_month=0<elapsed<n)
        for kind in ('ASP_INTERNAL','ASP_EXTERNAL','FORECAST_LATEST'):
            b=values(g.get(kind)); r[kind.lower()+'_achievement_pct']={m:pct(x,y) for m,x,y in zip(METRICS,a,b)}
            if kind.startswith('ASP'):
                r[kind.lower()+'_prorata_achievement_pct']={m:pct(x,y*Decimal(elapsed)/n if y is not None else None) for m,x,y in zip(METRICS,a,b)}
        for m,x,y in zip(METRICS,a,f):
            p=wape_parts[(k[0],k[1],m)]
            if x is None and y is None: continue
            if x is None or y is None: p[3]+=1; continue
            p[0]+=abs(x-y); p[1]+=abs(x); p[2]+=1
        output.append(r)
    wape=[]
    for (system,period,metric),(error,denom,matched,missing) in sorted(wape_parts.items()):
        value=pct(error,denom) if not missing else None
        wape.append(dict(source_system=system,bulan=period,metric=metric,wape_pct=value,matched_keys=matched,missing_keys=missing,accuracy_pct=None if value is None else str(Decimal(100)-Decimal(value)),provisional=period==observed.replace(day=1).isoformat()))
    return output,wape


def monthly_growth(orders, observed):
    # Compare observed DO only. No rows does not prove zero or source completeness.
    groups=defaultdict(list)
    for r in orders:
        if r['jenis_record']=='DO' and r['valid_analitik']:
            d=date.fromisoformat(r['tanggal_transaksi']); groups[(r['source_system'],d.replace(day=1),r['kode_produk'],r['kode_distributor'])].append((d,values(r)))
    def totals(k,limit):
        rr=[v for d,v in groups.get(k,[]) if d.day<=limit]
        return [sum((v[i] for v in rr),Decimal(0)) for i in range(3)] if rr else [None]*3
    result=[]
    for k in sorted(groups):
        system,d,product,dist=k; previous=date(d.year-(d.month==1),12 if d.month==1 else d.month-1,1); last_year=date(d.year-1,d.month,1)
        n=calendar.monthrange(d.year,d.month)[1]; partial=d==observed.replace(day=1)
        for label,ref in [('MOM',previous),('YOY',last_year)]:
            prior_n=calendar.monthrange(ref.year,ref.month)[1]; limit=min(observed.day,n,prior_n) if partial else n; prior_limit=limit if partial else prior_n
            a=totals(k,limit); b=totals((system,ref,product,dist),prior_limit)
            result.append(dict(source_system=system,bulan=d.isoformat(),kode_produk=product,kode_distributor=dist,comparison=label,reference_month=ref.isoformat(),mode='SAME_ELAPSED_DAYS' if partial else 'FULL_MONTH',current_days=limit,reference_days=prior_limit,growth_pct={m:pct(x-y,y) if x is not None and y is not None else None for m,x,y in zip(METRICS,a,b)}))
    return result


def preview(data,observed,cutoff,config):
    if config != {'version':2,'source_system':'MYSQL','source_business_timezone':'Asia/Jakarta','forecast_selection':'latest_timestamp_then_revision_then_source_id','steps':['order_preview','plan_history','monthly_metrics','monthly_growth']}:
        raise ValueError('konfigurasi V2 tidak didukung')
    if observed.tzinfo is None or cutoff.tzinfo is None or cutoff>observed: raise ValueError('cutoff rencana harus berzona dan <= snapshot')
    with localcontext() as ctx:
        ctx.prec=80
        order=order_preview(data,observed,yaml.safe_load(ORDER_CONFIG.read_text(encoding='utf-8')))
        plans,history=plan_history(data,observed,cutoff)
        monthly=order['actual_monthly']+plans
        metrics,wape=monthly_metrics(monthly,observed.astimezone(WIB).date())
        growth=monthly_growth(order['order_delivery'],observed.astimezone(WIB).date())
    order.update(scope='PLAN_AND_ACTUAL_V2',plan_cutoff_at=cutoff.isoformat(),monthly_metrics=monthly,forecast_history=history,achievement=metrics,wape=wape,growth=growth,source_coverage='NOT_VERIFIED',note='Preview berdasarkan snapshot saat ini; cutoff historis hanya seleksi rencana, bukan rekonstruksi actual. Bulan berjalan belum final; missing actual bukan nol. WAPE per source dan bulan, null bila pasangan tidak lengkap.')
    order['summary'].update(asp_internal_rows=sum(r['jenis_metrik']=='ASP_INTERNAL' for r in plans),asp_external_rows=sum(r['jenis_metrik']=='ASP_EXTERNAL' for r in plans),forecast_history_rows=len(history),forecast_latest_rows=sum(r['jenis_metrik']=='FORECAST_LATEST' for r in plans),monthly_metric_rows=len(monthly))
    return order


def run_preview(canonical_root,output_root,run_id,demo=False,plan_cutoff=None):
    if not RUN_ID.fullmatch(run_id): raise ValueError('run-id tidak valid')
    root=Path(canonical_root); manifest=root/'mysql'/run_id/'manifest.json'; digest=sha(manifest)
    data=read_run(root,run_id); m=json.loads(manifest.read_text(encoding='utf-8'))
    if sha(manifest)!=digest: raise ValueError('manifest berubah saat dibaca')
    observed=datetime.fromisoformat(m['snapshot_observed_at_utc']); observed=observed.replace(tzinfo=timezone.utc) if observed.tzinfo is None else observed.astimezone(timezone.utc)
    cfg=yaml.safe_load(CONFIG.read_text(encoding='utf-8'))
    result=preview(data,observed,plan_cutoff or observed,cfg)
    result.update(extract_run_id=run_id,synthetic=demo,canonical_manifest_sha256=digest,config_sha256=sha(CONFIG))
    root=Path(output_root)/('demo' if demo else 'mysql'); root.mkdir(parents=True,exist_ok=True)
    # Different cutoffs for one extraction remain separate; existing outputs never overwritten.
    suffix='' if plan_cutoff is None else '_plan_'+plan_cutoff.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    final=root/(run_id+suffix)
    if final.exists(): raise ValueError('preview sudah ada; gunakan run atau cutoff baru')
    temp=Path(tempfile.mkdtemp(prefix='.partial-',dir=root))
    try:
        (temp/'preview.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8'); temp.rename(final)
    finally:
        if temp.exists(): shutil.rmtree(temp)
    return result,final
