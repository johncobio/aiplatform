import pytest

from llm_service.model_store import ensure_model


def test_downloads_once_and_caches(tmp_path):
    src = tmp_path / "src" / "tiny.gguf"
    src.parent.mkdir()
    src.write_bytes(b"GGUF" * 100)
    url = src.as_uri()
    cache = tmp_path / "cache"

    path = ensure_model(url, cache)
    assert path == cache / "tiny.gguf"
    assert path.read_bytes() == b"GGUF" * 100
    assert not (cache / "tiny.gguf.part").exists()

    src.write_bytes(b"changed")
    assert ensure_model(url, cache).read_bytes() == b"GGUF" * 100  # cached, not re-fetched


def test_empty_download_is_rejected(tmp_path):
    src = tmp_path / "empty.gguf"
    src.write_bytes(b"")
    with pytest.raises(OSError, match="empty"):
        ensure_model(src.as_uri(), tmp_path / "cache")
