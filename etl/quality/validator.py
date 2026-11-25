"""Read-only quality gate for canonical V2; never authorizes loading."""
import json
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from etl.mapping.full_engine import sha
from etl.mapping.engine import RUN_ID

KEYS = dict(zip(('asp','asp_detail','delivery_order','delivery_order_detail','distributor','forecast','forecast_detail','harga_produk','produk','purchase_order','purchase_order_detail','revisi_forecast','revisi_forecast_detail'), ('id_asp','id_asp_detail','id_do','id_do_detail','kode_distributor','id_forecast','id_forecast_detail','id_harga','kode_produk','id_po','id_po_detail','id_revisi','id_revisi_detail')))
LINKS = {
 'asp': [('kode_distributor','distributor')],
 'asp_detail': [('id_asp','asp'),('kode_produk','produk')],
 'forecast': [('kode_distributor','distributor')],
 'forecast_detail': [('id_forecast','forecast'),('kode_produk','produk')],
 'revisi_forecast': [('id_forecast','forecast')],
 'revisi_forecast_detail': [('id_revisi','revisi_forecast'),('kode_produk','produk')],
 'harga_produk': [('kode_produk','produk')],
 'purchase_order': [('kode_distributor','distributor')],
 'purchase_order_detail': [('id_po','purchase_order'),('kode_produk','produk'),('id_harga','harga_produk')],
 'delivery_order': [('id_po','purchase_order')],
 'delivery_order_detail': [('id_do','delivery_order'),('id_po_detail','purchase_order_detail')],
}

def read_run(root, run_id):
    if not RUN_ID.fullmatch(run_id): raise ValueError('run-id tidak valid')
    folder = Path(root)/'mysql'/run_id
    m = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    if (m.get('scope'),m.get('mapping_version'),m.get('source_system'),m.get('extract_run_id')) != ('MYSQL_FULL',2,'MYSQL',run_id):
        raise ValueError('manifest Mapping V2 tidak cocok')
    if m.get('status') != 'SUCCESS' or m.get('quarantine') != 0: raise ValueError('Mapping belum bersih; hentikan validasi')
    expected = {t+'.jsonl' for t in KEYS}|{'quarantine.jsonl'}
    if set(m['output_files']) != expected or set(m['tables']) != set(KEYS): raise ValueError('dataset tidak lengkap')
    for file in expected:
        if sha(folder/file) != m['output_files'][file]: raise ValueError(f'checksum tidak cocok: {file}')
    if (folder/'quarantine.jsonl').stat().st_size: raise ValueError('karantina tidak kosong')
    data = {}
    for t, pk in KEYS.items():
        rows = [json.loads(line) for line in (folder/(t+'.jsonl')).read_text(encoding='utf-8').splitlines()]
        c = m['tables'][t]
        if c['ready'] != len(rows) or c['rows_read'] != len(rows) or c['quarantine'] != 0: raise ValueError(f'jumlah baris tidak cocok: {t}')
        if any(r.get('source_system')!='MYSQL' or r.get('mapping_status')!='READY' or not isinstance(r.get(pk),str) or not r[pk] for r in rows): raise ValueError(f'identitas canonical tidak valid: {t}')
        data[t] = rows
    n = sum(map(len,data.values()))
    if m['rows_read'] != n or m['ready'] != n: raise ValueError('total manifest tidak cocok')
    return data


def validate(data):
    issues = Counter()
    def issue(level, rule): issues[(level,rule)] += 1
    indexes = {}
    for t, pk in KEYS.items():
        idx = {}
        for r in data[t]:
            if r[pk] in idx: issue('ERROR','duplicate_pk:'+t)
            idx[r[pk]]=r
        indexes[t]=idx
    def get(t,k): return indexes[t].get(k)
    for t, links in LINKS.items():
        for r in data[t]:
            for field, target in links:
                if not get(target,r[field]): issue('ERROR',f'foreign_key:{t}.{field}')
    seen = set()
    def unique(rule,key):
        k=(rule,*key)
        if k in seen: issue('ERROR',rule)
        seen.add(k)
    for r in data['asp_detail']:
        h=get('asp',r['id_asp'])
        if h: unique('duplicate_asp',(h['tahun'],r['bulan'],h['kode_distributor'],r['kode_produk'],h['jenis_target']))
        if any(r[x] is None for x in ('target_pack','target_liter','target_rupiah','waktu_penetapan')): issue('WARNING','asp_incomplete')
    for r in data['forecast_detail']:
        h=get('forecast',r['id_forecast'])
        if h: unique('duplicate_forecast',(h['bulan_forecast'][:7],h['kode_distributor'],r['kode_produk']))
    for r in data['revisi_forecast_detail']:
        unique('duplicate_revision_product',(r['id_revisi'],r['kode_produk']))
        if any(r[x] is None for x in ('revisi_pack','revisi_liter','revisi_rupiah')): issue('ERROR','revision_incomplete')
    for r in data['revisi_forecast']:
        h=get('forecast',r['id_forecast'])
        if h and r['tanggal_revisi'] < h['tanggal_input']: issue('ERROR','revision_before_baseline')
    for r in data['purchase_order_detail']:
        h=get('harga_produk',r['id_harga']); po=get('purchase_order',r['id_po'])
        if h and h['kode_produk'] != r['kode_produk']: issue('ERROR','price_product_mismatch')
        if h and po and h['berlaku_mulai'] and h['berlaku_mulai'] > po['tanggal_po']: issue('ERROR','price_not_yet_effective')
        fields=('liter_per_pack_saat_po','harga_dasar_pack_saat_po','tarif_ppn_saat_po','harga_pack_setelah_ppn','qty_batal_pack')
        if any(r[x] is None for x in fields): issue('WARNING','po_snapshot_incomplete')
        if all(r[x] is not None for x in fields[1:4]):
            base,tax,final=(Decimal(r[x]) for x in fields[1:4])
            if (base*(1+tax)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)!=final: issue('ERROR','po_price_snapshot_inconsistent')
        if r['qty_batal_pack'] is not None and r['qty_batal_pack']>r['qty_pack']: issue('ERROR','cancel_exceeds_po')
    shipped=defaultdict(int)
    for r in data['delivery_order_detail']:
        h=get('delivery_order',r['id_do']); p=get('purchase_order_detail',r['id_po_detail'])
        unique('duplicate_do_line',(r['id_do'],r['nomor_baris']))
        if r['liter_per_pack_saat_do'] is None: issue('WARNING','do_snapshot_incomplete')
        if not h or not p: continue
        po=get('purchase_order',p['id_po'])
        if h['id_po'] != p['id_po']: issue('ERROR','do_po_mismatch'); continue
        if po and h['tanggal_do'] < po['tanggal_po']: issue('ERROR','delivery_before_order')
        # Only CONFIRMED was actually observed in audit. Others require review;
        # this is not a complete status policy or an actual-sales classifier.
        if h['status_do']=='CONFIRMED': shipped[p['id_po_detail']]+=r['qty_pack']
    for h in data['delivery_order']:
        if h['status_do']!='CONFIRMED': issue('WARNING','do_status_needs_policy')
    for h in data['purchase_order']:
        if h['status_po']!='PARTIAL': issue('WARNING','po_status_needs_policy')
    for key,qty in shipped.items():
        p=get('purchase_order_detail',key)
        if qty>p['qty_pack']: issue('ERROR','overdelivery')
        if p['qty_batal_pack'] is not None and qty+p['qty_batal_pack']>p['qty_pack']: issue('ERROR','shipped_plus_cancel_exceeds_po')
    errors=sum(v for (l,_),v in issues.items() if l=='ERROR')
    warnings=sum(v for (l,_),v in issues.items() if l=='WARNING')
    return {'status':'FAIL' if errors else 'REVIEW' if warnings else 'PASS','rows':sum(map(len,data.values())), 'errors':errors,'warnings':warnings,'issues':[{'level':l,'rule':r,'count':n} for (l,r),n in sorted(issues.items())], 'transaction_rows':sum(len(data[t]) for t in KEYS if t not in ('produk','distributor','harga_produk')), 'load_ready':False}
