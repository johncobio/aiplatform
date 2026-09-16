"""Download model artifacts into a local cache directory (idempotent)."""

import logging
import os
import shutil
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

_CHUNK = 8 * 1024 * 1024


def ensure_model(url: str, model_dir: Path) -> Path:
    """Return the local path for `url`, downloading it once if missing.

    Downloads go to a `.part` file and are renamed atomically, so a killed
    container never leaves a truncated file that looks complete.
    """
    model_dir.mkdir(parents=True, exist_ok=True)
    target = model_dir / url.rsplit("/", 1)[-1]
    if target.is_file() and target.stat().st_size > 0:
        log.info("model cached at %s (%.1f MB)", target, target.stat().st_size / 1e6)
        return target

    part = target.with_name(target.name + ".part")
    log.info("downloading %s -> %s", url, target)
    req = urllib.request.Request(url, headers={"User-Agent": "aiplatform-llm-service"})
    with urllib.request.urlopen(req, timeout=60) as resp, part.open("wb") as out:  # noqa: S310
        total = int(resp.headers.get("Content-Length") or 0)
        done, next_report = 0, 0.1
        while True:
            chunk = resp.read(_CHUNK)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if total and done / total >= next_report:
                log.info(
                    "download %d%% (%.0f/%.0f MB)", done * 100 // total, done / 1e6, total / 1e6
                )
                next_report += 0.1
        out.flush()
        os.fsync(out.fileno())
    if part.stat().st_size == 0:
        part.unlink(missing_ok=True)
        raise OSError(f"downloaded file is empty: {url}")
    shutil.move(part, target)
    log.info("download complete: %s (%.1f MB)", target, target.stat().st_size / 1e6)
    return target
