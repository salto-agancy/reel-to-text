import asyncio
from pathlib import Path

import httpx
import pytest

from reel_to_text.core.errors import (NotAVideo, ProviderUnavailable, RateLimited,
                                      ReelNotFound, ReelTooLong)
from reel_to_text.core.limits import RateLimiter
from reel_to_text.core.models import ReelMedia
from reel_to_text.core.service import ReelToText
from reel_to_text.core.store import Store
from reel_to_text.providers.transcription.base import SttResult
from reel_to_text.providers.transcription.deepgram import RemoteFetchFailed

URL = "https://www.instagram.com/reel/ABCDE12345/"


class FakeProvider:
    def __init__(self, name="fake", media=None, exc=None):
        self.name = name
        self.media = media
        self.exc = exc
        self.calls = 0

    async def get_reel(self, shortcode):
        self.calls += 1
        await asyncio.sleep(0.01)
        if self.exc:
            raise self.exc
        return self.media or ReelMedia(shortcode, "https://cdn.example/v.mp4", 30.0, "author", "cap", self.name)


class FakeStt:
    name = "fake-stt"

    def __init__(self, remote_fails=False):
        self.remote_fails = remote_fails
        self.url_calls = 0
        self.file_calls = []

    async def transcribe_url(self, url):
        self.url_calls += 1
        if self.remote_fails:
            raise RemoteFetchFailed("could not fetch")
        return SttResult("Привет мир.", "ru", 30.0)

    async def transcribe_file(self, path: Path, content_type):
        self.file_calls.append((path, path.exists(), path.stat().st_size))
        return SttResult("Из файла.", "ru", 30.0)


def make(tmp_path, providers=None, stt=None, per_hour=10, per_day=30, **kw):
    store = Store(tmp_path / "db.sqlite")
    return ReelToText(
        providers or [FakeProvider()], stt or FakeStt(), store,
        RateLimiter(store, per_hour, per_day), tmp_dir=tmp_path, **kw,
    )


async def test_happy_path_and_cache(tmp_path):
    prov, stt = FakeProvider(), FakeStt()
    core = make(tmp_path, [prov], stt)
    t = await core.transcribe(URL, "u1")
    assert t.text == "Привет мир." and t.shortcode == "ABCDE12345" and not t.cached
    assert t.stt_path == "remote_url" and t.author == "author"
    t2 = await core.transcribe("глянь " + URL, "u2")
    assert t2.cached and t2.text == t.text
    assert prov.calls == 1 and stt.url_calls == 1


async def test_concurrent_same_reel_paid_once(tmp_path):
    prov, stt = FakeProvider(), FakeStt()
    core = make(tmp_path, [prov], stt)
    a, b = await asyncio.gather(core.transcribe(URL, "u1"), core.transcribe(URL, "u2"))
    assert a.text == b.text
    assert prov.calls == 1 and stt.url_calls == 1


async def test_upload_fallback_and_cleanup(tmp_path):
    stt = FakeStt(remote_fails=True)
    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=b"x" * 1000))
    core = make(tmp_path, stt=stt, download_transport=transport)
    t = await core.transcribe(URL, "u1")
    assert t.text == "Из файла." and t.stt_path == "upload"
    path, existed, size = stt.file_calls[0]
    assert existed and size == 1000
    assert not path.exists()  # temp video removed


async def test_download_size_limit(tmp_path):
    stt = FakeStt(remote_fails=True)
    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=b"x" * (2 * 1024 * 1024)))
    core = make(tmp_path, stt=stt, download_transport=transport, max_download_mb=1)
    with pytest.raises(Exception, match="MAX_DOWNLOAD_MB"):
        await core.transcribe(URL, "u1")
    assert not list(tmp_path.glob("reel-*"))


async def test_too_long(tmp_path):
    prov = FakeProvider(media=ReelMedia("ABCDE12345", "u", 900.0))
    stt = FakeStt()
    core = make(tmp_path, [prov], stt, max_reel_seconds=300)
    with pytest.raises(ReelTooLong):
        await core.transcribe(URL, "u1")
    assert stt.url_calls == 0


async def test_rate_limit(tmp_path):
    core = make(tmp_path, per_hour=2)
    await core.transcribe("https://instagram.com/reel/AAAAA1/", "u1")
    await core.transcribe("https://instagram.com/reel/AAAAA2/", "u1")
    with pytest.raises(RateLimited):
        await core.transcribe("https://instagram.com/reel/AAAAA3/", "u1")
    # cached reels stay free, other users unaffected, admins unlimited
    await core.transcribe("https://instagram.com/reel/AAAAA1/", "u1")
    await core.transcribe("https://instagram.com/reel/AAAAA3/", "u2")
    await core.transcribe("https://instagram.com/reel/AAAAA4/", "u1", unlimited=True)


async def test_provider_chain(tmp_path):
    broken = FakeProvider("broken", exc=ProviderUnavailable("down"))
    good = FakeProvider("good")
    core = make(tmp_path, [broken, good])
    t = await core.transcribe(URL, "u1")
    assert t.instagram_provider == "good"


@pytest.mark.parametrize("exc", [ReelNotFound("x"), NotAVideo("x")])
async def test_final_errors_skip_other_providers(tmp_path, exc):
    first = FakeProvider("first", exc=exc)
    second = FakeProvider("second")
    core = make(tmp_path, [first, second])
    with pytest.raises(type(exc)):
        await core.transcribe(URL, "u1")
    assert second.calls == 0


async def test_all_providers_down(tmp_path):
    core = make(tmp_path, [FakeProvider(exc=ProviderUnavailable("a")), FakeProvider(exc=ProviderUnavailable("b"))])
    with pytest.raises(ProviderUnavailable):
        await core.transcribe(URL, "u1")
