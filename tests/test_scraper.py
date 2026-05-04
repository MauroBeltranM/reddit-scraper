"""Tests for RedditScraper._fetch_posts and _fetch_comments using httpx mocks."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.scraper import REDDIT_BASE, RedditScraper


# --- Helpers ---


def _make_request(url="https://www.reddit.com/"):
    """Build a fake httpx.Request for constructing valid responses."""
    return httpx.Request("GET", url)


def _make_posts_json_response(children, before=None, after=None):
    """Build a Reddit-style listing JSON response for posts."""
    return httpx.Response(
        200,
        json={
            "kind": "Listing",
            "data": {
                "before": before,
                "after": after,
                "children": children,
            },
        },
        request=_make_request(),
    )


def _make_t3(
    reddit_id="abc123",
    title="Test post",
    author="testuser",
    score=42,
    upvote_ratio=0.95,
    num_comments=7,
    url="https://example.com",
    selftext="",
    is_self=False,
    is_video=False,
    post_hint=None,
    permalink="/r/python/comments/abc123/test_post/",
):
    """Build a single t3 (post) child."""
    return {
        "kind": "t3",
        "data": {
            "id": reddit_id,
            "title": title,
            "author": author,
            "score": score,
            "upvote_ratio": upvote_ratio,
            "num_comments": num_comments,
            "url": url,
            "selftext": selftext,
            "is_self": is_self,
            "is_video": is_video,
            "post_hint": post_hint,
            "permalink": permalink,
        },
    }


def _make_comments_json_response(post_data, comments):
    """Build a Reddit-style [post_listing, comments_listing] JSON response."""
    return httpx.Response(
        200,
        json=[
            {
                "kind": "Listing",
                "data": {"children": [post_data]},
            },
            {
                "kind": "Listing",
                "data": {"children": comments},
            },
        ],
        request=_make_request(),
    )


def _make_t1(
    reddit_id="comm001",
    parent_id=None,
    author="commenter",
    score=5,
    body="Nice post!",
    replies=None,
):
    """Build a single t1 (comment) child."""
    data = {
        "id": reddit_id,
        "parent_id": parent_id,
        "author": author,
        "score": score,
        "body": body,
    }
    if replies is not None:
        data["replies"] = replies
    else:
        data["replies"] = ""
    return {"kind": "t1", "data": data}


# --- _fetch_posts tests ---


class TestFetchPosts:
    def test_fetch_posts_basic(self):
        """Should parse a valid Reddit JSON listing into post dicts."""
        scraper = RedditScraper()
        mock_resp = _make_posts_json_response([
            _make_t3(reddit_id="p1", title="First post", score=100),
            _make_t3(reddit_id="p2", title="Second post", score=50, is_self=True),
        ])

        with patch.object(scraper.client, "get", return_value=mock_resp):
            posts = scraper._fetch_posts("python")

        assert len(posts) == 2
        assert posts[0]["reddit_id"] == "p1"
        assert posts[0]["title"] == "First post"
        assert posts[0]["score"] == 100
        assert posts[0]["post_type"] == "link"

    def test_fetch_posts_detects_self_post(self):
        scraper = RedditScraper()
        mock_resp = _make_posts_json_response([
            _make_t3(reddit_id="sp1", is_self=True, selftext="Body"),
        ])

        with patch.object(scraper.client, "get", return_value=mock_resp):
            posts = scraper._fetch_posts("python")

        assert posts[0]["post_type"] == "self"

    def test_fetch_posts_detects_image_post(self):
        scraper = RedditScraper()
        mock_resp = _make_posts_json_response([
            _make_t3(reddit_id="img1", post_hint="image"),
        ])

        with patch.object(scraper.client, "get", return_value=mock_resp):
            posts = scraper._fetch_posts("python")

        assert posts[0]["post_type"] == "image"

    def test_fetch_posts_detects_video_post(self):
        scraper = RedditScraper()
        mock_resp = _make_posts_json_response([
            _make_t3(reddit_id="vid1", is_video=True),
        ])

        with patch.object(scraper.client, "get", return_value=mock_resp):
            posts = scraper._fetch_posts("python")

        assert posts[0]["post_type"] == "video"

    def test_fetch_posts_top_with_timeframe(self):
        """When sort=top, timeframe should be appended as &t= parameter."""
        scraper = RedditScraper()

        def assert_url(url):
            assert "/top.json" in url
            assert "t=week" in url
            return _make_posts_json_response([])

        with patch.object(scraper.client, "get", side_effect=assert_url):
            posts = scraper._fetch_posts("python", sort="top", timeframe="week")

        assert posts == []

    def test_fetch_posts_http_error_returns_empty(self):
        scraper = RedditScraper()
        mock_resp = httpx.Response(403, text="Forbidden", request=_make_request())
        mock_resp.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError(
            "403", request=mock_resp.request, response=mock_resp,
        ))

        with patch.object(scraper.client, "get", return_value=mock_resp):
            posts = scraper._fetch_posts("python")

        assert posts == []

    def test_fetch_posts_malformed_json_returns_empty(self):
        scraper = RedditScraper()
        mock_resp = httpx.Response(200, json={"not": "a listing"}, request=_make_request())

        with patch.object(scraper.client, "get", return_value=mock_resp):
            posts = scraper._fetch_posts("python")

        assert posts == []

    def test_fetch_posts_skips_non_t3_children(self):
        scraper = RedditScraper()
        mock_resp = _make_posts_json_response([
            {"kind": "t1", "data": {"id": "should_be_ignored"}},
            _make_t3(reddit_id="valid1"),
        ])

        with patch.object(scraper.client, "get", return_value=mock_resp):
            posts = scraper._fetch_posts("python")

        assert len(posts) == 1
        assert posts[0]["reddit_id"] == "valid1"

    def test_fetch_posts_empty_listing(self):
        scraper = RedditScraper()
        mock_resp = _make_posts_json_response([])

        with patch.object(scraper.client, "get", return_value=mock_resp):
            posts = scraper._fetch_posts("python")

        assert posts == []

    def test_fetch_posts_preserves_permalink(self):
        scraper = RedditScraper()
        mock_resp = _make_posts_json_response([
            _make_t3(reddit_id="p1", permalink="/r/python/comments/p1/my_post/"),
        ])

        with patch.object(scraper.client, "get", return_value=mock_resp):
            posts = scraper._fetch_posts("python")

        assert posts[0]["permalink"] == "/r/python/comments/p1/my_post/"


# --- _fetch_comments tests ---


class TestFetchComments:
    def test_fetch_comments_basic(self):
        scraper = RedditScraper()
        post_t3 = _make_t3(reddit_id="p1")
        comments = [_make_t1(reddit_id="c1", score=10, body="First")]
        mock_resp = _make_comments_json_response(post_t3, comments)

        with patch.object(scraper.client, "get", return_value=mock_resp):
            result = scraper._fetch_comments("/r/python/comments/p1/")

        assert len(result) == 1
        assert result[0]["reddit_id"] == "c1"
        assert result[0]["score"] == 10
        assert result[0]["body"] == "First"

    def test_fetch_comments_with_nested_replies(self):
        scraper = RedditScraper()
        post_t3 = _make_t3(reddit_id="p1")
        nested_replies = {
            "kind": "Listing",
            "data": {
                "children": [
                    _make_t1(reddit_id="c2", parent_id="t1_c1", score=3, body="Reply"),
                ],
            },
        }
        comments = [_make_t1(reddit_id="c1", score=10, body="Parent", replies=nested_replies)]
        mock_resp = _make_comments_json_response(post_t3, comments)

        with patch.object(scraper.client, "get", return_value=mock_resp):
            result = scraper._fetch_comments("/r/python/comments/p1/")

        assert len(result) == 2
        # First is parent (depth 0), second is reply (depth 1)
        parent = next(c for c in result if c["reddit_id"] == "c1")
        reply = next(c for c in result if c["reddit_id"] == "c2")
        assert parent["depth"] == 0
        assert reply["depth"] == 1
        assert reply["parent_reddit_id"] == "t1_c1"

    def test_fetch_comments_respects_top_comments_limit(self):
        scraper = RedditScraper(top_comments=2)
        post_t3 = _make_t3(reddit_id="p1")
        comments = [
            _make_t1(reddit_id=f"c{i}", score=10 - i, body=f"Comment {i}")
            for i in range(5)
        ]
        mock_resp = _make_comments_json_response(post_t3, comments)

        with patch.object(scraper.client, "get", return_value=mock_resp):
            result = scraper._fetch_comments("/r/python/comments/p1/")

        # Should only keep top 2 by score
        assert len(result) == 2
        scores = [c["score"] for c in result]
        assert max(scores) == 10

    def test_fetch_comments_respects_max_depth(self):
        scraper = RedditScraper(max_comment_depth=1)
        post_t3 = _make_t3(reddit_id="p1")
        # Depth 0 -> depth 1 -> depth 2 (should stop at depth 1)
        depth2_replies = {
            "kind": "Listing",
            "data": {
                "children": [
                    _make_t1(reddit_id="c3", parent_id="t1_c2", score=1, body="Too deep"),
                ],
            },
        }
        depth1_replies = {
            "kind": "Listing",
            "data": {
                "children": [
                    _make_t1(reddit_id="c2", parent_id="t1_c1", score=5, body="Reply", replies=depth2_replies),
                ],
            },
        }
        comments = [_make_t1(reddit_id="c1", score=10, body="Parent", replies=depth1_replies)]
        mock_resp = _make_comments_json_response(post_t3, comments)

        with patch.object(scraper.client, "get", return_value=mock_resp):
            result = scraper._fetch_comments("/r/python/comments/p1/")

        ids = [c["reddit_id"] for c in result]
        assert "c1" in ids  # depth 0
        assert "c2" in ids  # depth 1
        assert "c3" not in ids  # depth 2 exceeds max_comment_depth=1

    def test_fetch_comments_http_error_returns_empty(self):
        scraper = RedditScraper()
        mock_resp = httpx.Response(404, text="Not found", request=_make_request())
        mock_resp.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError(
            "404", request=mock_resp.request, response=mock_resp,
        ))

        with patch.object(scraper.client, "get", return_value=mock_resp):
            result = scraper._fetch_comments("/r/python/comments/missing/")

        assert result == []

    def test_fetch_comments_malformed_json_returns_empty(self):
        scraper = RedditScraper()
        mock_resp = httpx.Response(200, json={"error": "something"}, request=_make_request())

        with patch.object(scraper.client, "get", return_value=mock_resp):
            result = scraper._fetch_comments("/r/python/comments/bad/")

        assert result == []

    def test_fetch_comments_cleans_html(self):
        scraper = RedditScraper()
        post_t3 = _make_t3(reddit_id="p1")
        comments = [_make_t1(reddit_id="c1", body='<a href="https://example.com">link</a> text')]
        mock_resp = _make_comments_json_response(post_t3, comments)

        with patch.object(scraper.client, "get", return_value=mock_resp):
            result = scraper._fetch_comments("/r/python/comments/p1/")

        # _clean_html converts <a> to markdown link format
        assert "[link](https://example.com)" in result[0]["body"]

    def test_fetch_comments_empty_thread(self):
        scraper = RedditScraper()
        post_t3 = _make_t3(reddit_id="p1")
        mock_resp = _make_comments_json_response(post_t3, [])

        with patch.object(scraper.client, "get", return_value=mock_resp):
            result = scraper._fetch_comments("/r/python/comments/p1/")

        assert result == []

    def test_fetch_comments_skips_non_t1_children(self):
        scraper = RedditScraper()
        post_t3 = _make_t3(reddit_id="p1")
        comments = [
            {"kind": "t1", "data": {"id": "c1", "parent_id": None, "author": "u", "score": 1, "body": "ok", "replies": ""}},
            {"kind": "more", "data": {"count": 5, "children": ["c2", "c3"]}},
        ]
        mock_resp = _make_comments_json_response(post_t3, comments)

        with patch.object(scraper.client, "get", return_value=mock_resp):
            result = scraper._fetch_comments("/r/python/comments/p1/")

        assert len(result) == 1
        assert result[0]["reddit_id"] == "c1"


# --- Scraper init tests ---


class TestScraperInit:
    def test_default_params(self):
        scraper = RedditScraper()
        assert scraper.max_new_posts == 10
        assert scraper.top_comments == 50
        assert scraper.request_delay == 1.0
        assert scraper.max_comment_depth == 10

    def test_custom_params(self):
        scraper = RedditScraper(max_new_posts=5, top_comments=20, request_delay=0.5, max_comment_depth=5)
        assert scraper.max_new_posts == 5
        assert scraper.top_comments == 20
        assert scraper.request_delay == 0.5
        assert scraper.max_comment_depth == 5

    def test_client_has_user_agent(self):
        scraper = RedditScraper()
        assert "RedditScraper" in scraper.client.headers.get("user-agent", "")
        scraper.close()
