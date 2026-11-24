"""Source-agnostic extraction, atomic publication and shared locking."""
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from ..errors import ExtractError, ExtractBusy
from ..staging.writer import write_dataset

def run_adapter(adapter, root, batch_size=1000):
    if not 1 <= batch_size <= 10000:
        raise ExtractError("EXTRACT_BATCH_SIZE harus 1–10000.")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".extract.lock"
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise ExtractBusy("Extract sedang berjalan atau lock tertinggal.") from exc
    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    temp = root / (".partial-" + run_id)
    final = root / run_id
    try:
        temp.mkdir()
        with adapter.snapshot():
            plan, warnings = adapter.datasets()
            metadata = adapter.metadata()
            tables = []
            seen = set()
            for dataset in plan:
                if not re.fullmatch(r"[A-Za-z0-9_]+", dataset.name) or dataset.name.lower() in seen:
                    raise ExtractError("Nama dataset tidak valid atau duplikat.")
                seen.add(dataset.name.lower())
                tables.append(write_dataset(temp / (dataset.name + ".jsonl"), dataset,
                                            adapter.rows(dataset, batch_size)))
        manifest = {**metadata, "status": "SUCCESS", "mode": "FULL_EXTRACT", "run_id": run_id,
                    "source_type": adapter.source_type, "started_at_utc": started.isoformat(),
                    "finished_at_utc": datetime.now(timezone.utc).isoformat(), "tables": tables,
                    "total_rows": sum(t["rows"] for t in tables), "warnings": warnings}
        (temp / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.rename(final)  # Publish only a complete successful extraction.
        return manifest
    finally:
        try:
            if temp.exists():
                shutil.rmtree(temp)
        finally:
            lock.rmdir()

def latest(root):
    root = Path(root)
    if not root.exists():
        return None
    for folder in sorted(root.iterdir(), reverse=True):
        if folder.name.startswith(".") or not folder.is_dir():
            continue
        try:
            obj = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            if obj.get("status") == "SUCCESS":
                return obj
        except (OSError, ValueError):
            continue
    return None
