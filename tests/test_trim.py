from price_watch.fetch import FetchedPage
from price_watch.trim import trim_page

HTML = """<html><head><style>.x{}</style><script>var a=1;</script></head>
<body><nav><a href="/menu">Menu</a></nav>
<h1>Mac mini</h1><p>Price $1,359</p>
<a href="/item/1">View item</a><a href="#top">Top</a></body></html>"""


def page(body: str, content_type: str = "text/html; charset=utf-8") -> FetchedPage:
    return FetchedPage("https://shop.example.com/list", content_type, body)


def test_html_keeps_text_and_links_drops_noise() -> None:
    text = trim_page(page(HTML))
    assert text is not None
    assert "Mac mini" in text and "$1,359" in text
    assert "View item (https://shop.example.com/item/1)" in text.replace("\n", " ")
    assert "var a" not in text and ".x{}" not in text and "Menu" not in text
    assert "#top" not in text


def test_json_and_feeds_pass_through() -> None:
    assert trim_page(page('{"a": 1}', "application/json")) == '{"a": 1}'
    assert trim_page(page("<rss><item/></rss>", "application/rss+xml")) == "<rss><item/></rss>"


def test_cut_at_limit() -> None:
    text = trim_page(page("x" * 100, "application/json"), max_characters=10)
    assert text == "x" * 10


def test_nothing_usable_returns_none() -> None:
    assert trim_page(page("<html><script>x</script></html>")) is None
    assert trim_page(page("   ", "application/json")) is None
    assert trim_page(page("binary", "image/png")) is None


def test_html_sniffed_without_content_type() -> None:
    assert trim_page(page("<!doctype html><p>hi</p>", "")) == "hi"
