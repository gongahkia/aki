"""Terminal frame capture utilities for demo screenshot workflows."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


def capture_terminal_frame(
    content: str,
    *,
    title: str = "demo",
    output_dir: str = "asset/reference/demo",
    metadata: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Persist a terminal frame snapshot and metadata with timestamped filenames."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_title = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in title)
    base = f"{safe_title}-{timestamp}"

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    txt_path = out_dir / f"{base}.txt"
    meta_path = out_dir / f"{base}.json"

    txt_path.write_text(content, encoding="utf-8")
    payload = {
        "title": title,
        "timestamp_utc": timestamp,
        "content_path": str(txt_path),
    }
    if metadata:
        payload.update({str(k): str(v) for k, v in metadata.items()})
    meta_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return {
        "content_path": str(txt_path),
        "metadata_path": str(meta_path),
    }
