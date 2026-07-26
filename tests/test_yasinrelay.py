"""
tests/test_yasinrelay.py
پوشش تست برای: fetch_engine (Fake/Subprocess)، ai_processor،
eitaa_publisher (با requests mock)، و pipeline کامل.
"""

from unittest.mock import Mock, patch

import pytest

from yasinrelay.ai_processor import CallableProcessor, PassthroughProcessor
from yasinrelay.config import EitaaConfig
from yasinrelay.eitaa_publisher import EitaaPublisher, PublishError
from yasinrelay.fetch_engine import FakeFetcher, FetchError, Post, SubprocessFetcher
from yasinrelay.pipeline import Pipeline


# ---------------------------------------------------------------------------
# FetchEngine
# ---------------------------------------------------------------------------

def test_fake_fetcher_returns_added_posts():
    fetcher = FakeFetcher()
    fetcher.add_posts("@news", [Post(channel="@news", message_id="1", text="hello")])
    posts = fetcher.fetch("@news")
    assert len(posts) == 1
    assert posts[0].text == "hello"


def test_fake_fetcher_respects_limit():
    fetcher = FakeFetcher()
    fetcher.add_posts(
        "@news",
        [Post(channel="@news", message_id=str(i), text=f"post{i}") for i in range(5)],
    )
    posts = fetcher.fetch("@news", limit=2)
    assert len(posts) == 2


def test_fake_fetcher_unknown_channel_returns_empty():
    fetcher = FakeFetcher()
    assert fetcher.fetch("@unknown") == []


def test_subprocess_fetcher_missing_binary_raises():
    fetcher = SubprocessFetcher(binary_path="/nonexistent/binary")
    with pytest.raises(FetchError):
        fetcher.fetch("@news")


# ---------------------------------------------------------------------------
# ContentProcessor
# ---------------------------------------------------------------------------

def test_passthrough_processor_keeps_text():
    post = Post(channel="@news", message_id="1", text="سلام دنیا")
    processed = PassthroughProcessor().process(post)
    assert processed.text == "سلام دنیا"
    assert processed.source_post is post


def test_callable_processor_applies_transform():
    post = Post(channel="@news", message_id="1", text="hello")
    processed = CallableProcessor(lambda t: t.upper()).process(post)
    assert processed.text == "HELLO"


# ---------------------------------------------------------------------------
# EitaaPublisher
# ---------------------------------------------------------------------------

def _make_publisher(delay: int = 0) -> EitaaPublisher:
    config = EitaaConfig(token="TESTTOKEN", channel="@my_channel")
    return EitaaPublisher(config, inter_message_delay_seconds=delay)


def test_publisher_raises_without_token():
    config = EitaaConfig(token="", channel="@my_channel")
    publisher = EitaaPublisher(config)
    from yasinrelay.ai_processor import PassthroughProcessor as _PP

    post = Post(channel="@news", message_id="1", text="hi")
    content = _PP().process(post)
    with pytest.raises(PublishError):
        publisher.publish(content)


@patch("yasinrelay.eitaa_publisher.requests.post")
def test_publisher_success(mock_post):
    mock_post.return_value = Mock(status_code=200, text="ok")
    publisher = _make_publisher()

    post = Post(channel="@news", message_id="1", text="hi")
    content = PassthroughProcessor().process(post)
    result = publisher.publish(content)

    assert result.success is True
    called_url = mock_post.call_args[0][0]
    assert "TESTTOKEN" in called_url
    assert "sendMessage" in called_url


@patch("yasinrelay.eitaa_publisher.requests.post")
def test_publisher_uses_sendfile_when_media_present(mock_post):
    mock_post.return_value = Mock(status_code=200, text="ok")
    publisher = _make_publisher()

    post = Post(channel="@news", message_id="1", text="hi", media_url="http://example.com/img.jpg")
    content = PassthroughProcessor().process(post)
    publisher.publish(content)

    called_url = mock_post.call_args[0][0]
    assert "sendFile" in called_url


@patch("yasinrelay.eitaa_publisher.requests.post")
def test_publisher_reports_http_failure(mock_post):
    mock_post.return_value = Mock(status_code=500, text="server error")
    publisher = _make_publisher()

    post = Post(channel="@news", message_id="1", text="hi")
    content = PassthroughProcessor().process(post)
    result = publisher.publish(content)

    assert result.success is False
    assert "500" in result.error


# ---------------------------------------------------------------------------
# Pipeline (end-to-end با fake/mocked اجزا)
# ---------------------------------------------------------------------------

@patch("yasinrelay.eitaa_publisher.requests.post")
def test_pipeline_runs_full_flow(mock_post):
    mock_post.return_value = Mock(status_code=200, text="ok")

    fetcher = FakeFetcher()
    fetcher.add_posts(
        "@news",
        [
            Post(channel="@news", message_id="1", text="post one"),
            Post(channel="@news", message_id="2", text="post two"),
        ],
    )
    processor = PassthroughProcessor()
    publisher = _make_publisher()

    pipeline = Pipeline(fetcher, processor, publisher)
    report = pipeline.run_channel("@news")

    assert report.fetched == 2
    assert report.published == 2
    assert report.errors == []


def test_pipeline_reports_fetch_error():
    fetcher = SubprocessFetcher(binary_path="/nonexistent/binary")
    processor = PassthroughProcessor()
    publisher = _make_publisher()

    pipeline = Pipeline(fetcher, processor, publisher)
    report = pipeline.run_channel("@news")

    assert report.fetched == 0
    assert report.published == 0
    assert len(report.errors) == 1
