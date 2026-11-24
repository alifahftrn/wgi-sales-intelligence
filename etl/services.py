from django.conf import settings
from django.db import connections
from .adapters.factory import create_adapter
from .engine.extract_engine import run_adapter
from .errors import ExtractError

def extract(source='mysql', file=None):
    if source == 'mysql':
        connection = connections['default']
        try:
            adapter = create_adapter(source, connection=connection, file=file)
            return run_adapter(adapter, settings.EXTRACT_ROOT, settings.EXTRACT_BATCH_SIZE)
        finally:
            connection.close()
    if source == 'excel':
        adapter = create_adapter(source, file=file)
        return run_adapter(adapter, settings.EXTRACT_ROOT.parent / 'extracts_excel', settings.EXTRACT_BATCH_SIZE)
    raise ExtractError('Sumber tidak didukung.')
