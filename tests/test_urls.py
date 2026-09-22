import pytest

from reel_to_text.core.errors import InvalidUrl
from reel_to_text.core.urls import extract_shortcode, find_url


@pytest.mark.parametrize("text,code", [
    ("https://www.instagram.com/reel/DdOH1iLKWX9/", "DdOH1iLKWX9"),
    ("https://instagram.com/reel/DdOH1iLKWX9", "DdOH1iLKWX9"),
    ("https://www.instagram.com/reels/DdOH1iLKWX9/?igsh=abc123", "DdOH1iLKWX9"),
    ("https://www.instagram.com/p/CA2aJYrg6cZ/", "CA2aJYrg6cZ"),
    ("https://www.instagram.com/someuser/reel/DdOH1iLKWX9/", "DdOH1iLKWX9"),
    ("Смотри какой ролик https://www.instagram.com/reel/Dd-OH_1i/?utm_source=ig_web_copy_link круто", "Dd-OH_1i"),
    ("http://m.instagram.com/tv/ABCDEF123/", "ABCDEF123"),
])
def test_extract(text, code):
    assert extract_shortcode(text) == code
    assert find_url(text)


@pytest.mark.parametrize("text", [
    "", "привет", "https://youtube.com/shorts/abc", "https://www.instagram.com/someuser/",
    "https://www.instagram.com/stories/user/123/",
])
def test_invalid(text):
    assert find_url(text) is None
    with pytest.raises(InvalidUrl):
        extract_shortcode(text)
