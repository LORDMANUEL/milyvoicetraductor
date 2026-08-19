import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mily_ai.external_sources import (
    download_external_pack,
    validate_external_pack_url,
)
from mily_ai.models import ModelOperationError


class FakeResponse:
    def __init__(self, payload: bytes, url: str, content_length: int | None = None):
        self._stream = io.BytesIO(payload)
        self._url = url
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class ExternalSourceTests(unittest.TestCase):
    def test_only_https_mmpack_from_github_or_huggingface_is_allowed(self):
        accepted = (
            "https://github.com/acme/models/releases/download/v1/fast.mmpack",
            "https://release-assets.githubusercontent.com/file/fast.mmpack",
            "https://huggingface.co/acme/model/resolve/0123456789abcdef/fast.mmpack",
            "https://cdn-lfs.huggingface.co/repo/fast.mmpack",
        )
        for url in accepted:
            with self.subTest(url=url):
                self.assertEqual(validate_external_pack_url(url), url)

    def test_private_untrusted_or_executable_urls_are_rejected(self):
        rejected = (
            "http://github.com/acme/fast.mmpack",
            "https://localhost/fast.mmpack",
            "https://127.0.0.1/fast.mmpack",
            "https://github.com@evil.example/fast.mmpack",
            "https://user:password@github.com/fast.mmpack",
            "https://example.com/fast.mmpack",
            "https://github.com/acme/model.py",
            "file:///tmp/fast.mmpack",
        )
        for url in rejected:
            with self.subTest(url=url):
                with self.assertRaises(ModelOperationError) as captured:
                    validate_external_pack_url(url)
                self.assertEqual(captured.exception.code, "MODEL_EXTERNAL_SOURCE")

    def test_download_streams_to_staging_and_validates_redirect_host(self):
        initial = "https://github.com/acme/models/releases/download/v1/fast.mmpack"
        final = "https://release-assets.githubusercontent.com/acme/fast.mmpack"
        with tempfile.TemporaryDirectory() as tmp, patch(
            "mily_ai.external_sources.urlopen",
            return_value=FakeResponse(b"PK-safe-data", final, 12),
        ):
            path = download_external_pack(initial, Path(tmp), max_bytes=1024)
            self.assertEqual(path.read_bytes(), b"PK-safe-data")
            self.assertEqual(path.suffix, ".mmpack")

    def test_download_aborts_when_stream_exceeds_limit(self):
        url = "https://huggingface.co/acme/model/resolve/main/fast.mmpack"
        with tempfile.TemporaryDirectory() as tmp, patch(
            "mily_ai.external_sources.urlopen",
            return_value=FakeResponse(b"x" * 32, url),
        ):
            with self.assertRaises(ModelOperationError) as captured:
                download_external_pack(url, Path(tmp), max_bytes=16)
            self.assertEqual(captured.exception.code, "MODEL_EXTERNAL_TOO_LARGE")
            self.assertFalse(any(Path(tmp).iterdir()))


if __name__ == "__main__":
    unittest.main()
