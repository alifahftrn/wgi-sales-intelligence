"""Order/delivery preview V1. No database writes, no historical reconstruction."""
import json
import shutil
import tempfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from pathlib import Path

import yaml
from etl.mapping.full_engine import sha
from etl.mapping.engine import RUN_ID
from etl.quality.validator import KEYS, read_run, validate

CONFIG = Path(__file__).resolve().parents[1] / 'configurations' / 'order_transform_v1.yaml'
PO_STATUSES = {'OPEN', 'PARTIAL', 'COMPLETED', 'CANCELLED'}
DO_STATUSES = {'CONFIRMED', 'CANCELLED'}
STATUS_WARNINGS = {'po_status_needs_policy', 'do_status_needs_policy'}
WIB = timezone(timedelta(hours=7))


def validate_orders(ctx):
    data = ctx['data']
    quality = validate(data)
    # V1 quality predates the agreed policy. Recheck status explicitly here;
    # never ignore any other quality issue.
    if any(r['status_po'] not in PO_STATUSES for r in data['purchase_order']):
        raise ValueError('status PO tidak dikenal/NULL')
    if any(r['status_do'] not in DO_STATUSES for r in data['delivery_order']):
        raise ValueError('status DO tidak dikenal/NULL')
    issues = [i for i in quality['issues'] if not (i['level'] == 'WARNING' and i['rule'] in STATUS_WARNINGS)]
    if issues:
        raise ValueError('quality gate: ' + ', '.join(i['rule'] for i in issues))
    for table, field in [('purchase_order','tanggal_po'), ('delivery_order','tanggal_do')]:
        if any(date.fromisoformat(r[field]) > ctx['snapshot_date'] for r in data[table]):
            raise ValueError('tanggal transaksi melewati tanggal snapshot WIB')
    ctx['index'] = {t: {r[pk]:r for r in data[t]} for t,pk in KEYS.items()}


def join_orders(ctx):
    d, idx = ctx['data'], ctx['index']
    by_po = defaultdict(list)
    by_do = defaultdict(list)
    shipped = defaultdict(int)
    for line in d['purchase_order_detail']:
        by_po[line['id_po']].append(line)
    for line in d['delivery_order_detail']:
        by_do[line['id_do']].append(line)
        if idx['delivery_order'][line['id_do']]['status_do'] == 'CONFIRMED':
            shipped[line['id_po_detail']] += line['qty_pack']
    if any(not by_do[h['id_do']] for h in d['delivery_order']):
        raise ValueError('DO tanpa detail; perlu review')
    valid = {}
    for h in d['purchase_order']:
        lines = by_po[h['id_po']]
        if not lines:
            raise ValueError('PO tanpa detail; perlu review')
        qty = sum(p['qty_pack'] for p in lines)
        sent = sum(shipped[p['id_po_detail']] for p in lines)
        cancel = sum(p['qty_batal_pack'] for p in lines)
        if sent + cancel > qty:
            raise ValueError('pengiriman ditambah pembatalan melebihi PO')
        expected = ('COMPLETED' if sent == qty else
                    'CANCELLED' if sent + cancel == qty else
                    'PARTIAL' if sent else 'OPEN')
        if h['status_po'] != expected:
            raise ValueError('status PO tidak konsisten dengan saldo; perlu review')
        valid[h['id_po']] = not (sent == 0 and cancel == qty)
    orders, actual, snapshots = [], [], []
    for p in d['purchase_order_detail']:
        h = idx['purchase_order'][p['id_po']]
        q, s, c = p['qty_pack'], shipped[p['id_po_detail']], p['qty_batal_pack']
        eligible = valid[h['id_po']]
        price = Decimal(p['harga_pack_setelah_ppn'])
        volume = Decimal(p['liter_per_pack_saat_po'])
        common = dict(source_system='MYSQL', id_po_sumber=h['id_po'], id_po_detail_sumber=p['id_po_detail'],
                      no_po=h['no_po'], tanggal_po=h['tanggal_po'], kode_produk=p['kode_produk'],
                      kode_distributor=h['kode_distributor'], harga_pack_setelah_ppn=str(price),
                      id_harga_sumber=p['id_harga'], harga_dasar_pack=p['harga_dasar_pack_saat_po'],
                      tarif_ppn=p['tarif_ppn_saat_po'])
        orders.append(dict(common, jenis_record='PO', id_detail_sumber=p['id_po_detail'],
                           tanggal_transaksi=h['tanggal_po'], status_sumber=h['status_po'], valid_analitik=eligible,
                           qty_pack=q, qty_batal_pack=c, liter_per_pack=str(volume),
                           total_liter=str(q*volume), total_rupiah=str(q*price)))
        bod = q-s if eligible else 0
        operational = q-s-c if eligible else 0
        snapshots.append(dict(common, status_po=h['status_po'], valid_analitik=eligible, qty_po_pack=q,
                              qty_do_pack=s, qty_batal_pack=c, qty_outstanding_bod=bod,
                              qty_outstanding_eligible=operational, liter_per_pack=str(volume),
                              outstanding_bod_liter=str(bod*volume), outstanding_bod_rupiah=str(bod*price),
                              aging_hari=(ctx['snapshot_date']-date.fromisoformat(h['tanggal_po'])).days,
                              tanggal_snapshot=ctx['snapshot_date'].isoformat(), cutoff_at=ctx['cutoff'].isoformat(),
                              alasan_outstanding=h['alasan_tidak_terkirim'], keterangan_outstanding=h['keterangan_outstanding']))
    for line in d['delivery_order_detail']:
        h = idx['delivery_order'][line['id_do']]
        p = idx['purchase_order_detail'][line['id_po_detail']]
        po = idx['purchase_order'][p['id_po']]
        qty = line['qty_pack']; volume = Decimal(line['liter_per_pack_saat_do']); price = Decimal(p['harga_pack_setelah_ppn'])
        row = dict(source_system='MYSQL', jenis_record='DO', id_detail_sumber=line['id_do_detail'],
                   id_do_sumber=h['id_do'], no_do=h['no_do'], id_po_sumber=po['id_po'], no_po=po['no_po'],
                   id_po_detail_sumber=p['id_po_detail'], tanggal_po=po['tanggal_po'], tanggal_transaksi=h['tanggal_do'],
                   kode_produk=p['kode_produk'], kode_distributor=po['kode_distributor'], status_sumber=h['status_do'],
                   valid_analitik=h['status_do']=='CONFIRMED' and valid[po['id_po']], qty_pack=qty, qty_batal_pack=None,
                   liter_per_pack=str(volume), harga_pack_setelah_ppn=str(price), id_harga_sumber=p['id_harga'],
                   harga_dasar_pack=p['harga_dasar_pack_saat_po'], tarif_ppn=p['tarif_ppn_saat_po'],
                   total_liter=str(qty*volume), total_rupiah=str(qty*price))
        orders.append(row)
        if row['valid_analitik']:
            actual.append(row)
    ctx.update(orders=orders, actual=actual, snapshots=snapshots)


def aggregate_actual(ctx):
    groups = defaultdict(lambda: [0, Decimal(0), Decimal(0)])
    for r in ctx['actual']:
        key = (r['source_system'],r['tanggal_transaksi'][:7]+'-01',r['kode_produk'],r['kode_distributor'])
        a = groups[key]; a[0] += r['qty_pack']; a[1] += Decimal(r['total_liter']); a[2] += Decimal(r['total_rupiah'])
    ctx['monthly'] = [dict(source_system=k[0],bulan=k[1],kode_produk=k[2],kode_distributor=k[3],
                           jenis_metrik='ACTUAL',qty_pack=v[0],total_liter=str(v[1]),total_rupiah=str(v[2]))
                      for k,v in sorted(groups.items())]


REGISTRY = {'validate_orders':validate_orders, 'join_orders':join_orders, 'aggregate_actual':aggregate_actual}


def preview(data, cutoff, config):
    if config != {'version':1,'source_system':'MYSQL','po_statuses':['OPEN','PARTIAL','COMPLETED','CANCELLED'],
                  'do_statuses':['CONFIRMED','CANCELLED'],'steps':list(REGISTRY)}:
        raise ValueError('konfigurasi V1 tidak didukung; dependency dan policy harus sesuai')
    if cutoff.tzinfo is None:
        raise ValueError('cutoff harus memiliki zona waktu')
    ctx = dict(data=data,cutoff=cutoff,snapshot_date=cutoff.astimezone(WIB).date())
    with localcontext() as dc:
        dc.prec=80
        for name in config['steps']:
            REGISTRY[name](ctx)
        s = [r for r in ctx['snapshots'] if r['valid_analitik']]
        a = ctx['actual']; po=sum(r['qty_po_pack'] for r in s); shipped=sum(r['qty_do_pack'] for r in s)
        summary = dict(po_valid_pack=po, actual_pack=sum(r['qty_pack'] for r in a),
                       actual_liter=str(sum((Decimal(r['total_liter']) for r in a),Decimal(0))),
                       actual_rupiah=str(sum((Decimal(r['total_rupiah']) for r in a),Decimal(0))),
                       outstanding_bod_pack=sum(r['qty_outstanding_bod'] for r in s),
                       outstanding_eligible_pack=sum(r['qty_outstanding_eligible'] for r in s),
                       fulfillment_pct=str((Decimal(shipped)*100/po).quantize(Decimal('.01'))) if po else None,
                       order_rows=len(ctx['orders']), monthly_rows=len(ctx['monthly']), snapshot_rows=len(ctx['snapshots']))
    return {'status':'PREVIEW_ONLY','scope':'ORDER_DELIVERY_ACTUAL_V1','load_ready':False,
            'cutoff_at':cutoff.isoformat(),'snapshot_date_wib':ctx['snapshot_date'].isoformat(),
            'summary':summary,'order_delivery':ctx['orders'],'actual_monthly':ctx['monthly'],'outstanding_snapshot':ctx['snapshots']}


def run_preview(canonical_root, output_root, run_id, demo=False):
    if not RUN_ID.fullmatch(run_id): raise ValueError('run-id tidak valid')
    canonical_root=Path(canonical_root); folder=canonical_root/'mysql'/run_id
    manifest=folder/'manifest.json'; digest=sha(manifest)
    data=read_run(canonical_root,run_id)
    m=json.loads(manifest.read_text(encoding='utf-8'))
    # Demo flag must agree with the isolated source root used by the command.
    if sha(manifest)!=digest: raise ValueError('manifest berubah saat dibaca')
    stamp=datetime.fromisoformat(m['snapshot_observed_at_utc'])
    if stamp.tzinfo is None: stamp=stamp.replace(tzinfo=timezone.utc)  # field explicitly UTC
    stamp=stamp.astimezone(timezone.utc)
    config=yaml.safe_load(CONFIG.read_text(encoding='utf-8'))
    result=preview(data,stamp,config)
    result.update(extract_run_id=run_id,synthetic=demo,canonical_manifest_sha256=digest,config_sha256=sha(CONFIG))
    root=Path(output_root)/('demo' if demo else 'mysql'); root.mkdir(parents=True,exist_ok=True)
    final=root/run_id
    if final.exists(): raise ValueError('preview sudah ada; gunakan run Extract baru')
    temp=Path(tempfile.mkdtemp(prefix='.partial-',dir=root))
    try:
        (temp/'preview.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        temp.rename(final)
    finally:
        if temp.exists(): shutil.rmtree(temp)
    return result,final
