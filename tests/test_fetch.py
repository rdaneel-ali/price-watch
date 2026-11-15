import httpx
import pytest

from price_watch.fetch import FetchError, PageTooLargeError, fetch_url, make_client


def client_for(handler: httpx.MockTransport) -> httpx.Client:
    return make_client(handler)


def test_fetches_body_and_content_type() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text="hello", headers={"content-type": "text/html"})
    )
    page = fetch_url(client_for(transport), "https://example.com/a")
    assert page.body == "hello"
    assert page.content_type == "text/html"


def test_sends_generic_user_agent() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["user-agent"])
        return httpx.Response(200, text="x")

    fetch_url(client_for(httpx.MockTransport(handler)), "https://example.com")
    assert seen[0].startswith("price-watch/")


def test_rejects_non_https() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200))
    with pytest.raises(FetchError):
        fetch_url(client_for(transport), "http://example.com")


def test_non_200_fails() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(404))
    with pytest.raises(FetchError):
        fetch_url(client_for(transport), "https://example.com")


def test_network_error_becomes_fetch_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    with pytest.raises(FetchError):
        fetch_url(client_for(httpx.MockTransport(handler)), "https://example.com")


def test_limit_enforced_while_streaming() -> None:
    def stream() -> httpx.SyncByteStream:
        class Chunks(httpx.SyncByteStream):
            def __iter__(self):  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
                for _ in range(10):
                    yield b"x" * 100

        return Chunks()

    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=stream()))
    with pytest.raises(PageTooLargeError):
        fetch_url(client_for(transport), "https://example.com", max_bytes=450)


def test_declared_content_length_over_limit_fails_early() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text="x", headers={"content-length": "999999"})
    )
    with pytest.raises(PageTooLargeError):
        fetch_url(client_for(transport), "https://example.com", max_bytes=100)


def test_body_exactly_at_limit_is_allowed() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 100))
    assert len(fetch_url(client_for(transport), "https://example.com", max_bytes=100).body) == 100


def test_follows_https_redirects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "/new"})
        return httpx.Response(200, text="moved")

    page = fetch_url(client_for(httpx.MockTransport(handler)), "https://example.com/old")
    assert page.body == "moved"


def test_refuses_redirect_to_http() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"location": "http://example.com/x"})
    )
    with pytest.raises(FetchError):
        fetch_url(client_for(transport), "https://example.com")


def test_redirect_loop_fails() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"location": "https://example.com/again"})
    )
    with pytest.raises(FetchError):
        fetch_url(client_for(transport), "https://example.com")


def test_cookies_are_not_kept() -> None:
    cookies_sent: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cookies_sent.append(request.headers.get("cookie"))
        return httpx.Response(200, text="x", headers={"set-cookie": "a=b"})

    client = client_for(httpx.MockTransport(handler))
    fetch_url(client, "https://example.com")
    fetch_url(client, "https://example.com")
    assert cookies_sent == [None, None]
