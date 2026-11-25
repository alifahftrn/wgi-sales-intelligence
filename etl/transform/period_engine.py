"""Period analysis over validated V2 data; never writes to databases."""
import calendar
import hashlib
import json
import shutil
import tempfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP, localcontext
from pathlib import Path

import yaml
from etl.mapping.engine import RUN_ID
from etl.mapping.full_engine import sha
from etl.quality.validator import read_run
from etl.transform.order_engine import WIB
from etl.transform.plan_engine import CONFIG, FIELDS, METRICS, pct, preview as preview_v2

DAY = timedelta(days=1)
KINDS = {'month':1, 'quarter':3, 'semester':6, 'year':12, 'ytd':12}
FILTERS = {'product':('produk','kode_produk','kode_produk'),
           'distributor':('distributor','kode_distributor','kode_distributor'),
           'region':('distributor','kode_distributor','region'),
           'area':('distributor','kode_distributor','area'),
           'brand':('produk','kode_produk','brand')}


def shift_month(d, n):
    year, month = divmod(d.year*12+d.month-1+n,12)
    month += 1
    return date(year,month,min(d.day,calendar.monthrange(year,month)[1]))


def period_bounds(kind, year=None, index=None, start=None, end=None):
    if kind=='custom':
        if year is not None or index is not None or start is None or end is None:
            raise ValueError('custom membutuhkan --start dan --end saja')
        if start>end or start.year<1901 or end.year>9998 or (end-start).days>3660:
            raise ValueError('rentang custom tidak valid (maksimum 3661 hari)')
        return start,end
    if kind not in KINDS or type(year) is not int or not 1901<=year<=9998 or start is not None or end is not None:
        raise ValueError('periode/tahun tidak valid')
    width=KINDS[kind]
    if width==12:
        if index is not None: raise ValueError('year/YTD tidak memakai --index')
        index=1
    elif type(index) is not int or not 1<=index<=12//width:
        raise ValueError('index periode tidak valid')
    first=date(year,1+(index-1)*width,1)
    return first,shift_month(first,width)-DAY


def comparison_bounds(kind, start, end, compare):
    if compare=='none': return None
    if compare=='yoy' or (kind=='ytd' and compare=='previous'):
        a=shift_month(start,-12)
        if kind=='custom': return a,shift_month(end,-12)
        return a,shift_month(a,KINDS[kind])-DAY
    if compare!='previous': raise ValueError('comparison tidak valid')
    if kind=='custom': return start-(end-start+DAY),start-DAY
    a=shift_month(start,-KINDS[kind]); return a,start-DAY


def windows(kind, requested, observed, compare, mode):
    if mode not in ('elapsed','full'): raise ValueError('comparison mode tidak valid')
    start,end=requested
    if start>observed: raise ValueError('periode mulai setelah snapshot')
    current=(start,min(end,observed)); ref=comparison_bounds(kind,start,end,compare)
    if ref is None: return current,None
    if ref[0]>observed: raise ValueError('periode pembanding setelah snapshot')
    reference=(ref[0],min(ref[1],observed))
    # On partial current periods compare equal elapsed calendar days; completed
    # periods use full calendar spans (e.g. February vs March).
    if mode=='elapsed' and current[1]<end:
        count=min((current[1]-current[0]).days,(reference[1]-reference[0]).days)
        current=(current[0],current[0]+timedelta(days=count))
        reference=(reference[0],reference[0]+timedelta(days=count))
    return current,reference


def decimal_values(r): return tuple(Decimal(str(r[f])) for f in FIELDS)

def render(values):
    return {m: None if x is None else format(x.quantize(Decimal('0.000001'),rounding=ROUND_HALF_UP),'f') for m,x in zip(METRICS,values)}

def key(r,month): return (r['source_system'],month,r['kode_produk'],r['kode_distributor'])

def totals(groups):
    return [sum((v[i] for v in groups.values()),Decimal(0)) for i in range(3)] if groups else [None]*3

def ratio(a,b): return dict(zip(METRICS,(pct(x,y) for x,y in zip(a,b))))


def analyze_window(result, data, span, filters):
    start,end=span
    indexes={t:{r[pk]:r for r in data[t]} for t,pk in [('produk','kode_produk'),('distributor','kode_distributor')]}
    def allowed(r):
        for name,value in filters.items():
            table,pk,field=FILTERS[name]
            if indexes[table][r[pk]][field]!=value: return False
        return True
    actual=defaultdict(lambda:[Decimal(0)]*3)
    for r in result['order_delivery']:
        if r['jenis_record']!='DO' or not r['valid_analitik'] or not allowed(r): continue
        d=date.fromisoformat(r['tanggal_transaksi'])
        if start<=d<=end:
            a=actual[key(r,d.replace(day=1).isoformat())]
            for i,x in enumerate(decimal_values(r)): a[i]+=x
    plans={kind:{} for kind in ('ASP_INTERNAL','ASP_EXTERNAL')}
    for r in result['monthly_metrics']:
        kind=r['jenis_metrik']
        if kind not in plans or not allowed(r): continue
        first=date.fromisoformat(r['bulan']); last=shift_month(first,1)-DAY
        overlap=(min(last,end)-max(first,start)).days+1
        if overlap<=0: continue
        factor=Decimal(overlap)/Decimal(last.day)
        k=key(r,r['bulan'])
        if k in plans[kind]: raise ValueError('ASP duplikat pada periode')
        # Ratios remain unrounded until rendered; pack prorata can be fractional.
        plans[kind][k]=[v*factor for v in decimal_values(r)]
    a=totals(actual)
    report={'start':start.isoformat(),'end':end.isoformat(),'days':(end-start).days+1,
            'actual':render(a),'actual_key_months':len(actual),'asp':{}}
    for kind,group in plans.items():
        b=totals(group); missing_actual=len(group.keys()-actual.keys()); missing_target=len(actual.keys()-group.keys())
        report['asp'][kind]={'prorata_target':render(b),'target_key_months':len(group),
             'missing_actual_keys':missing_actual,'missing_target_keys':missing_target,
             'achievement_pct':ratio(a,b) if not (missing_actual or missing_target) else ratio([None]*3,[None]*3)}
    return report,a


def period_preview(data,observed,plan_cutoff,kind,year=None,index=None,start=None,end=None,compare='yoy',mode='elapsed',filters=None):
    filters=filters or {}
    if set(filters)-FILTERS.keys() or any(not isinstance(x,str) or not x.strip() for x in filters.values()):
        raise ValueError('filter tidak valid')
    if compare not in ('none','yoy','previous'): raise ValueError('comparison tidak valid')
    if observed.tzinfo is None: raise ValueError('snapshot harus berzona')
    requested=period_bounds(kind,year,index,start,end)
    current,reference=windows(kind,requested,observed.astimezone(WIB).date(),compare,mode)
    base=preview_v2(data,observed,plan_cutoff,yaml.safe_load(CONFIG.read_text(encoding='utf-8')))
    with localcontext() as ctx:
        ctx.prec=80
        cur,a=analyze_window(base,data,current,filters)
        ref,b=analyze_window(base,data,reference,filters) if reference else (None,[None]*3)
        growth={m:pct(x-y,y) if x is not None and y is not None else None for m,x,y in zip(METRICS,a,b)}
    return {'status':'PREVIEW_ONLY','scope':'PERIOD_ANALYSIS_V3','load_ready':False,
            'snapshot_date_wib':observed.astimezone(WIB).date().isoformat(),'snapshot_at':observed.isoformat(),
            'plan_cutoff_at':plan_cutoff.isoformat(),'source_coverage':'NOT_VERIFIED',
            'period':kind,'requested_start':requested[0].isoformat(),'requested_end':requested[1].isoformat(),
            'compare':compare,'mode':mode,'filters':filters,'dimension_policy':'CURRENT_OBSERVED_ATTRIBUTES',
            'current':cur,'reference':ref,'growth_pct':growth,
            'note':'Actual pada snapshot, bukan rekonstruksi historis. Hari snapshot dapat belum lengkap. Tidak ada baris bukan nol. ASP prorata hanya target tersedia; cakupan belum terverifikasi. Forecast/WAPE dan outstanding tetap di V1/V2.'}


def run_preview(canonical_root,output_root,run_id,demo=False,plan_cutoff=None,**query):
    if not RUN_ID.fullmatch(run_id): raise ValueError('run-id tidak valid')
    root=Path(canonical_root); manifest=root/'mysql'/run_id/'manifest.json'; digest=sha(manifest)
    data=read_run(root,run_id); meta=json.loads(manifest.read_text(encoding='utf-8'))
    if sha(manifest)!=digest: raise ValueError('manifest berubah saat dibaca')
    observed=datetime.fromisoformat(meta['snapshot_observed_at_utc'])
    observed=observed.replace(tzinfo=timezone.utc) if observed.tzinfo is None else observed.astimezone(timezone.utc)
    result=period_preview(data,observed,plan_cutoff or observed,**query)
    result.update(extract_run_id=run_id,synthetic=demo,canonical_manifest_sha256=digest,v2_config_sha256=sha(CONFIG))
    identity={k:result[k] for k in ('period','requested_start','requested_end','compare','mode','filters','plan_cutoff_at')}
    token=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:16]
    root=Path(output_root)/('demo' if demo else 'mysql'); root.mkdir(parents=True,exist_ok=True)
    final=root/(run_id+'_'+token)
    if final.exists(): raise ValueError('preview periode sudah ada; gunakan query atau run baru')
    temp=Path(tempfile.mkdtemp(prefix='.partial-',dir=root))
    try:
        (temp/'preview.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        temp.rename(final)
    finally:
        if temp.exists(): shutil.rmtree(temp)
    return result,final
