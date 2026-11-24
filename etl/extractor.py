"""Compatibility facade for existing tests, commands and monitoring."""
from .errors import ExtractError, ExtractBusy
from .adapters.mysql_adapter import MySQLAdapter
from .engine.extract_engine import run_adapter, latest

def run(connection, root, batch_size=1000):
    return run_adapter(MySQLAdapter(connection), root, batch_size)
