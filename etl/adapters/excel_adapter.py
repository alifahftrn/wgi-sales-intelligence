"""Read an explicitly configured .xlsx sheet, without executing formulas."""
from contextlib import contextmanager
from pathlib import Path
from hashlib import sha256
import shutil
import tempfile
from .base import BaseAdapter, Dataset
from ..errors import ExtractError

class ExcelAdapter(BaseAdapter):
    source_type = "excel"
    def __init__(self, path, config):
        self.path = Path(path)
        self.config = config

    @contextmanager
    def snapshot(self):
        from openpyxl import load_workbook
        if self.path.suffix.lower() != '.xlsx' or not self.path.is_file():
            raise ExtractError('Pilih file .xlsx lokal yang tersedia.')
        if self.path.stat().st_size > 50 * 1024 * 1024:
            raise ExtractError('File Excel demo maksimal 50 MB.')
        # Work on a private copy so parsing and checksum refer to the same bytes.
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / 'source.xlsx'
            shutil.copyfile(self.path, copy)
            with copy.open('rb') as stream:
                self.digest = sha256(stream.read()).hexdigest()
            wb = load_workbook(copy, read_only=True, data_only=False, keep_links=False)
            try:
                if self.config['sheet'] not in wb.sheetnames:
                    raise ExtractError(f"Sheet wajib tidak ada: {self.config['sheet']}")
                self.sheet = wb[self.config['sheet']]
                yield self
            finally:
                wb.close()
                self.sheet = None

    def datasets(self):
        expected = tuple(self.config['columns'])
        header = next(self.sheet.iter_rows(min_row=1, max_row=1, values_only=True), ())
        if tuple(header) != expected:
            raise ExtractError(f"Header Excel harus tepat: {', '.join(expected)}")
        return [Dataset(self.config['name'], expected, {'sheet': self.config['sheet'], 'source_types': 'Excel cell values'})], []

    def rows(self, dataset, batch_size):
        for row in self.sheet.iter_rows(min_row=2):
            if all(cell.value is None for cell in row):
                continue
            if len(row) != len(dataset.columns):
                raise ExtractError('Jumlah kolom Excel tidak sesuai konfigurasi.')
            if any(cell.data_type in ('f', 'e') for cell in row):
                raise ExtractError('Rumus atau error cell tidak didukung; gunakan values only.')
            yield dict(zip(dataset.columns, (cell.value for cell in row)))

    def metadata(self):
        return {'source_file': self.path.name, 'source_sha256': self.digest,
                'time_note': 'Excel cell values as parsed; no business transformation.'}
