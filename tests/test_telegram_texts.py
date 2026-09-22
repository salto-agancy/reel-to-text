from reel_to_text.core.errors import RateLimited, ReelTooLong
from reel_to_text.core.models import Transcript
from reel_to_text.interfaces.telegram import texts


def tr(text, **kw):
    return Transcript(text=text, source_url="https://www.instagram.com/reel/A/", shortcode="A", **kw)


def test_short():
    msgs = texts.render(tr("Привет.", author="bob", duration=65))
    assert msgs == ["Привет.\n\n— @bob · 1:05"]


def test_empty_speech():
    assert texts.render(tr("   "))[0].startswith("В ролике не нашлось речи")


def test_long_split_respects_limit():
    body = "\n\n".join(("Предложение номер %d. " % i) * 30 for i in range(12))
    msgs = texts.render(tr(body, author="bob"))
    assert 1 < len(msgs) <= texts.MAX_MESSAGES
    assert all(len(m) <= texts.TG_LIMIT for m in msgs)
    assert msgs[-1].rstrip().endswith(f"[{len(msgs)}/{len(msgs)}]")
    joined = " ".join(m.rsplit("\n\n[", 1)[0] for m in msgs)
    assert "Предложение номер 11." in joined


def test_very_long_goes_to_file():
    body = "слово " * 5000
    assert texts.render(tr(body)) == []
    assert "Источник:" in texts.txt_file(tr(body))


def test_split_without_spaces():
    chunks = texts.split_text("x" * 10000, 3900)
    assert [len(c) for c in chunks] == [3900, 3900, 2200]


def test_errors():
    assert "2:00" in texts.error_text(ReelTooLong(120, 90)) or "1:30" in texts.error_text(ReelTooLong(120, 90))
    assert "мин" in texts.error_text(RateLimited(600))
