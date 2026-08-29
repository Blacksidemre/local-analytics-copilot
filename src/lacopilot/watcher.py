from __future__ import annotations

import json
import time
from pathlib import Path

from lacopilot.audit import audit
from lacopilot.config import get_settings
from lacopilot.tools.common import safe_output_path
from lacopilot.workflows import full_dataset_review

SUPPORTED = {".csv", ".xlsx", ".xlsm", ".parquet", ".pq"}


def process_new_file(path: Path) -> dict:
    s = get_settings()
    rel = str(path.resolve().relative_to(s.workspace.resolve()))
    review = full_dataset_review(
        rel,
        question="Yeni gelen veri setini kalite, yapı ve olası analizler açısından incele.",
        create_dashboard=False,
    )
    out = safe_output_path(path.stem + "_auto_review.json", ".json")
    out.write_text(json.dumps(review, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    audit(
        s.logs_dir,
        "watcher_processed",
        file=rel,
        output=str(out.resolve().relative_to(s.workspace.resolve())),
    )
    return {"file": rel, "output": str(out.resolve().relative_to(s.workspace.resolve()))}


def watch_incoming() -> None:
    """Watch workspace/incoming and create a deterministic review for newly created supported files."""
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError as exc:
        raise RuntimeError("Watcher için: pip install -e '.[watch]'") from exc
    s = get_settings()

    class Handler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory:
                return
            p = Path(event.src_path)
            if p.suffix.lower() not in SUPPORTED:
                return
            time.sleep(1.0)
            try:
                process_new_file(p)
            except Exception as exc:
                audit(s.logs_dir, "watcher_error", file=str(p), error=str(exc))

    obs = Observer()
    obs.schedule(Handler(), str(s.incoming_dir), recursive=False)
    obs.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()
