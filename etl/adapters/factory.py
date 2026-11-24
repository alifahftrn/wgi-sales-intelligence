from pathlib import Path
from ..errors import ExtractError
from .mysql_adapter import MySQLAdapter
from .excel_adapter import ExcelAdapter

def create_adapter(source, *, connection=None, file=None):
    if source == 'mysql' and connection is not None and file is None:
        return MySQLAdapter(connection)
    if source == 'excel' and file is not None:
        import yaml
        path = Path(__file__).resolve().parent.parent / 'configurations' / 'excel_sales.yaml'
        config = yaml.safe_load(path.read_text(encoding='utf-8'))
        return ExcelAdapter(file, config)
    raise ExtractError('Sumber atau parameter tidak sesuai. Excel memerlukan --file.')
