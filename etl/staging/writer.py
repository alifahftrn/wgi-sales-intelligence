"""Lossless JSONL writer shared by source adapters."""
import hashlib
import json
from datetime import date, datetime, time
from decimal import Decimal
from ..errors import ExtractError

def json_value(value):
    if isinstance(value, Decimal):
        return str(value)  # Preserve exact money/quantity; never float.
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    raise TypeError(f"Unsupported type: {type(value).__name__}")

def write_dataset(path, dataset, rows):
    digest = hashlib.sha256()
    count = 0
    with path.open("wb") as output:
        for row in rows:
            if set(row) != set(dataset.columns):
                raise ExtractError(f"Kolom baris tidak sesuai dataset {dataset.name}.")
            line = (json.dumps(row, ensure_ascii=False, default=json_value, allow_nan=False) + "\n").encode("utf-8")
            output.write(line)
            digest.update(line)
            count += 1
    return {"table": dataset.name, "file": path.name, "rows": count,
            "sha256": digest.hexdigest(), "columns": list(dataset.columns), **dataset.metadata}
