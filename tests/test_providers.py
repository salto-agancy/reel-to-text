import json

import httpx
import pytest

from reel_to_text.core.errors import NotAVideo, ProviderUnavailable, ReelNotFound, TranscriptionFailed
from reel_to_text.providers.instagram.hikerapi import HikerApiProvider
from reel_to_text.providers.transcription.deepgram import DeepgramStt, RemoteFetchFailed


def hiker(handler):
    return HikerApiProvider("KEY", transport=httpx.MockTransport(handler))


async def test_hikerapi_ok():
    seen = {}

    def handler(req):
        seen["path"] = req.url.path
        seen["code"] = req.url.params["code"]
        seen["key"] = req.headers["x-access-key"]
        return httpx.Response(200, json={
            "code": "ABC", "media_type": 2, "video_url": "https://cdn/v.mp4", "video_duration": 42.5,
            "caption_text": "cap", "user": {"username": "someone"},
        })

    m = await hiker(handler).get_reel("ABC")
    assert seen == {"path": "/v1/media/by/code", "code": "ABC", "key": "KEY"}
    assert (m.video_url, m.duration, m.author, m.caption) == ("https://cdn/v.mp4", 42.5, "someone", "cap")


async def test_hikerapi_carousel_video():
    body = {"media_type": 8, "video_url": None, "resources": [
        {"media_type": 1}, {"media_type": 2, "video_url": "https://cdn/c.mp4", "video_duration": 10}]}
    m = await hiker(lambda r: httpx.Response(200, json=body)).get_reel("ABC")
    assert m.video_url == "https://cdn/c.mp4" and m.duration == 10


async def test_hikerapi_photo():
    with pytest.raises(NotAVideo):
        await hiker(lambda r: httpx.Response(200, json={"media_type": 1, "video_url": None})).get_reel("A")


async def test_hikerapi_404():
    with pytest.raises(ReelNotFound):
        await hiker(lambda r: httpx.Response(404, json={"detail": "not found"})).get_reel("A")


@pytest.mark.parametrize("status", [401, 402, 429, 500])
async def test_hikerapi_unavailable(status):
    with pytest.raises(ProviderUnavailable):
        await hiker(lambda r: httpx.Response(status, text="x")).get_reel("A")


DG_OK = {
    "metadata": {"duration": 12.3},
    "results": {"channels": [{"alternatives": [{
        "transcript": "раз два",
        "languages": ["ru"],
        "paragraphs": {"paragraphs": [
            {"sentences": [{"text": "Раз."}, {"text": "Два."}]},
            {"sentences": [{"text": "Три."}]},
        ]},
    }]}]},
}


async def test_deepgram_remote_url():
    seen = {}

    def handler(req):
        seen["params"] = dict(req.url.params)
        seen["body"] = json.loads(req.content)
        seen["auth"] = req.headers["authorization"]
        return httpx.Response(200, json=DG_OK)

    stt = DeepgramStt("K", transport=httpx.MockTransport(handler))
    r = await stt.transcribe_url("https://cdn/v.mp4")
    assert r.text == "Раз. Два.\n\nТри." and r.language == "ru" and r.duration == 12.3
    assert seen["body"] == {"url": "https://cdn/v.mp4"} and seen["auth"] == "Token K"
    assert seen["params"]["model"] == "nova-3" and seen["params"]["language"] == "multi"


async def test_deepgram_remote_fetch_failed():
    stt = DeepgramStt("K", transport=httpx.MockTransport(
        lambda r: httpx.Response(400, json={"err_msg": "Could not determine if URL for media download is publicly routable."})))
    with pytest.raises(RemoteFetchFailed):
        await stt.transcribe_url("https://cdn/v.mp4")


async def test_deepgram_auth_error():
    stt = DeepgramStt("K", transport=httpx.MockTransport(lambda r: httpx.Response(401, text="bad key")))
    with pytest.raises(TranscriptionFailed):
        await stt.transcribe_url("https://cdn/v.mp4")


async def test_deepgram_file(tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"data")
    seen = {}

    def handler(req):
        seen["ct"] = req.headers["content-type"]
        seen["body"] = req.content
        return httpx.Response(200, json=DG_OK)

    r = await DeepgramStt("K", transport=httpx.MockTransport(handler)).transcribe_file(f, "video/mp4")
    assert seen == {"ct": "video/mp4", "body": b"data"} and r.text.startswith("Раз.")
