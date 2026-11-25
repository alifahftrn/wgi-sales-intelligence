"""Canonical product V1: map only, never create SCD versions or write DBs."""
from decimal import Decimal, InvalidOperation

FIELDS = ('kode_produk', 'kode_apc_lama', 'nama_produk', 'brand',
          'jenis_produk', 'segment', 'kemasan_liter', 'isi_karton', 'liter_per_karton')
REQUIRED = set(FIELDS) - {'kode_apc_lama'}
CORE = {'kode_produk', 'nama_produk', 'liter_per_karton'}

class MappingError(ValueError):
    pass

def code(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise MappingError('kode harus teks atau integer')
    value = str(value).strip()
    if not value:
        raise MappingError('kode kosong')
    return value

def decimal_value(value, precision, scale):
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
        raise MappingError('angka desimal tidak valid')
    try:
        d = Decimal(value)
        if not d.is_finite() or not 0 < d < Decimal(10) ** (precision-scale):
            raise MappingError('angka di luar rentang positif')
        q = d.quantize(Decimal(1).scaleb(-scale))
        if q != d:
            raise MappingError('presisi desimal melebihi schema; tidak dibulatkan')
        return format(q, 'f')
    except InvalidOperation as exc:
        raise MappingError('angka desimal tidak valid') from exc

def pack_size(value):
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
        raise MappingError('isi_karton harus integer')
    try:
        d = Decimal(value)
        if not d.is_finite() or not 0 < d <= 2147483647 or d != d.to_integral_value():
            raise MappingError('isi_karton harus integer positif dalam rentang PostgreSQL')
        return int(d)
    except InvalidOperation as exc:
        raise MappingError('isi_karton tidak valid') from exc

def text(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise MappingError('teks kosong atau panjang melebihi schema')
    return value.strip()

def map_product(row, profile):
    mapping = profile['fields']
    out = {'source_system': profile['source_system']}
    for field in FIELDS:
        value = row.get(mapping[field]) if field in mapping else None
        if value is None:
            out[field] = None
            continue
        try:
            if field in ('kode_produk', 'kode_apc_lama'):
                out[field] = code(value)
            elif field == 'isi_karton':
                out[field] = pack_size(value)
            elif field in ('kemasan_liter', 'liter_per_karton'):
                out[field] = decimal_value(value, 10 if field == 'kemasan_liter' else 12, 3)
            else:
                out[field] = text(value, {'nama_produk':150,'brand':50,'jenis_produk':10,'segment':20}[field])
        except MappingError as exc:
            raise MappingError(f'{field}: {exc}') from exc
    missing = sorted(f for f in REQUIRED if out[f] is None)
    if CORE.intersection(missing):
        raise MappingError('atribut inti wajib belum lengkap: ' + ', '.join(missing))
    if out['jenis_produk'] is not None and out['jenis_produk'] not in ('2W','4W'):
        raise MappingError('jenis_produk di luar domain 2W/4W')
    if out['segment'] is not None and out['segment'] not in ('Top','Mid','Low'):
        raise MappingError('segment di luar domain Top/Mid/Low')
    if out['kemasan_liter'] is not None and out['isi_karton'] is not None:
        if Decimal(out['kemasan_liter'])*out['isi_karton'] != Decimal(out['liter_per_karton']):
            raise MappingError('liter_per_karton tidak sama dengan kemasan_liter x isi_karton')
    if profile['source_system'] == 'MYSQL' and missing:
        raise MappingError('atribut wajib MySQL belum lengkap: ' + ', '.join(missing))
    return {**out, 'mapping_status': 'INCOMPLETE' if missing else 'READY', 'missing_fields': missing}
