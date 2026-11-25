"""Synthetic raw fixture, isolated from real extracts and databases."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from etl.schema import BASE, OPTIONAL_COLUMNS
from etl.mapping.full_engine import map_full_run


def fixture():
    rows={t:[] for t in BASE}
    def add(t,**values):
        r=dict.fromkeys(BASE[t]+OPTIONAL_COLUMNS[t]); r.update(updated_at='2026-11-25T01:00:00',**values); rows[t].append(r)
    add('produk',kodeProduk=99001,namaProduk='DEMO PRODUK',kemasanProduk='0.800',isiKarton=12,volumeTotal='9.600',jenisProduk='2W',brand='DEMO',segment='Top')
    add('distributor',kodeDistributor=99001,namaDistributor='DEMO DISTRIBUTOR',area='Jawa',region='Region 1',wilayah='DEMO')
    add('harga_produk',idHarga=1,kodeProduk=99001,areaHarga='Jawa',berlakuMulai='2025-01-01',hargaBoxSebelumPPN='100000.00')
    for i,year,month,qty,delivered,cancel in [(1,2025,11,100,100,0),(2,2026,10,120,100,0),(3,2026,11,150,90,10)]:
        day=f'{year}-{month:02d}-01'
        add('purchase_order',idPO=i,noPO=f'DEMO-PO-{i}',tanggalPO=day,kodeDistributor=99001,statusPO='PARTIAL' if delivered<qty else 'COMPLETED',alasanTidakTerkirim='Stock' if delivered<qty else None)
        add('purchase_order_detail',idPODetail=i,idPO=i,kodeProduk=99001,idHarga=1,qtyPack=qty,qtyBatalPack=cancel,literPerPackSaatPO='9.600',hargaDasarPackSaatPO='100000.00',tarifPPNSaatPO='0.110000',hargaPackSetelahPPN='111000.00')
        for j,amount in enumerate([delivered] if i!=3 else [40,50],1):
            k=i*10+j
            add('delivery_order',idDO=k,noDO=f'DEMO-DO-{k}',tanggalDO=f'{year}-{month:02d}-{j+1:02d}',idPO=i,statusDO='CONFIRMED')
            add('delivery_order_detail',idDODetail=k,idDO=k,nomorBaris=1,idPODetail=i,qtyPack=amount,literPerPackSaatDO='9.600')
    for i,kind in enumerate(['Internal','External'],1):
        pack=100 if i==1 else 120
        add('asp',idASP=i,tahun=2026,jenisTarget=kind,kodeDistributor=99001,tanggalInput='2026-01-01T08:00:00')
        add('asp_detail',idASPDetail=i,idASP=i,bulan=11,kodeProduk=99001,targetPack=pack,targetLiter=str(pack*96//10),targetRupiah=str(pack*111000),waktuPenetapan='2026-01-01T08:00:00')
    add('forecast',idForecast=1,bulanForecast='2026-11-01',kodeDistributor=99001,tanggalInput='2026-10-25T08:00:00')
    add('forecast_detail',idForecastDetail=1,idForecast=1,kodeProduk=99001,forecastPack=110,forecastLiter='1056',forecastRupiah='12210000')
    for i,day,pack in [(1,3,100),(2,10,95)]:
        add('revisi_forecast',idRevisi=i,idForecast=1,mingguKe=i,tanggalRevisi=f'2026-11-{day:02d}T08:00:00')
        add('revisi_forecast_detail',idRevisiDetail=i,idRevisi=i,kodeProduk=99001,revisiPack=pack,revisiLiter=str(pack*96//10),revisiRupiah=str(pack*111000))
    return rows


def create_demo(root):
    root=Path(root); now=datetime.now(timezone.utc); run=now.strftime('%Y%m%dT%H%M%SZ_')+uuid4().hex[:8]
    raw=root/'extracts'/run; raw.mkdir(parents=True,exist_ok=False)
    tables=[]
    for t,rows in fixture().items():
        b=''.join(json.dumps(r)+'\n' for r in rows).encode('utf-8'); (raw/(t+'.jsonl')).write_bytes(b)
        tables.append({'table':t,'file':t+'.jsonl','columns':BASE[t]+OPTIONAL_COLUMNS[t],'rows':len(rows),'sha256':hashlib.sha256(b).hexdigest()})
    (raw/'manifest.json').write_text(json.dumps({'status':'SUCCESS','source_type':'mysql','run_id':run,'tables':tables,'synthetic':True,'snapshot_observed_at_utc':now.isoformat(),'started_at_utc':now.isoformat(),'finished_at_utc':now.isoformat()}),encoding='utf-8')
    map_full_run(root/'extracts',root/'canonical_v2',run)
    return run
