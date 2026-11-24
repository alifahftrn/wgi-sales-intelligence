"""Create synthetic test input only, never reads corporate data."""
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Create a synthetic Excel fixture under .local/demo.'
    requires_system_checks = []
    def handle(self, *args, **options):
        from openpyxl import Workbook
        path = settings.BASE_DIR / '.local' / 'demo' / 'produk_demo.xlsx'
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            self.stdout.write(f'Demo already exists: {path}')
            return
        wb = Workbook()
        ws = wb.active
        ws.title = 'Produk'
        ws.append(['Product Code', 'Product Name', 'Volume per Carton'])
        ws.append(['DEMO-001', 'Produk Demo A', 12])
        ws.append(['DEMO-002', 'Produk Demo B', 9.6])
        ws.append(['DEMO-003', 'Produk Demo C', 24])
        wb.save(path)
        self.stdout.write(self.style.SUCCESS('Demo dibuat: .local/demo/produk_demo.xlsx (3 baris fiktif)'))
