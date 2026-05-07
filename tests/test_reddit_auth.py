"""Tests for reddit_auth service: token fetch, caching, refresh, invalidate, and OAuth disabled."""

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services import reddit_auth
from app.services.reddit_auth import (
    _request_token,
    get_reddit_token,
    invalidate_token,
)


# --- Helpers ---


def _make_request(url="https://www.reddit.com/api/v1/access_token"):
    """Build a fake httpx.Request for constructing valid responses."""
    return httpx.Request("POST", url)


def _make_token_response(access_token="test_token_123", expires_in=3600, status_code=200):
    """Build a fake Reddit token endpoint response."""
    return httpx.Response(
        status_code,
        json={
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": expires_in,
            "scope": "*",
        },
        request=_make_request(),
    )


@pytest.fixture(autouse=True)
def _reset_cache():
    """Reset the module-level token cache and lock state before each test."""
    reddit_auth._cached_token = None
    reddit_auth._expires_at = 0.0


# --- Token fetch tests ---


class TestRequestToken:
    @patch("app.services.reddit_auth.settings")
    @patch("app.services.reddit_auth.httpx.post")
    def test_fetch_token_success(self, mock_post, mock_settings):
        """Should request token via client_credentials grant and return (token, expires_at)."""
        mock_settings.reddit_oauth_enabled = True
        mock_post.return_value = _make_token_response(access_token="abc123", expires_in=3600)

        result = _request_token()

        assert result is not None
        token, expires_at = result
        assert token == "abc123"
        # expires_at should be roughly now + 3600 - 60 (safety margin)
        expected_approx = time.time() + 3540
        assert abs(expires_at - expected_approx) < 2  # within 2s tolerance

        # Verify correct endpoint and auth
        call_args = mock_post.call_args
        assert "access_token" in call_args.args[0]
        assert call_args.kwargs["auth"] == (
            reddit_auth.REDDIT_CLIENT_ID,
            reddit_auth.REDDIT_CLIENT_SECRET,
        )
        assert call_args.kwargs["data"]["grant_type"] == "client_credentials"

    @patch("app.services.reddit_auth.settings")
    @patch("app.services.reddit_auth.httpx.post")
    def test_fetch_token_returns_none_when_oauth_disabled(self, mock_post, mock_settings):
        """Should return None without making any HTTP call when OAuth is disabled."""
        mock_settings.reddit_oauth_enabled = False

        result = _request_token()

        assert result is None
        mock_post.assert_not_called()

    @patch("app.services.reddit_auth.settings")
    @patch("app.services.reddit_auth.httpx.post")
    def test_fetch_token_returns_none_on_http_error(self, mock_post, mock_settings):
        """Should return None gracefully on HTTP errors (e.g. 401 bad credentials)."""
        mock_settings.reddit_oauth_enabled = True
        mock_resp = httpx.Response(401, text="Unauthorized", request=_make_request())
        mock_post.return_value = mock_resp

        result = _request_token()

        assert result is None

    @patch("app.services.reddit_auth.settings")
    @patch("app.services.reddit_auth.httpx.post")
    def test_fetch_token_returns_none_on_network_error(self, mock_post, mock_settings):
        """Should return None on connection/network errors."""
        mock_settings.reddit_oauth_enabled = True
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        result = _request_token()

        assert result is None

    @patch("app.services.reddit_auth.settings")
    @patch("app.services.reddit_auth.httpx.post")
    def test_fetch_token_returns_none_when_response_missing_token(self, mock_post, mock_settings):
        """Should return None if Reddit response JSON has no access_token field."""
        mock_settings.reddit_oauth_enabled = True
        mock_post.return_value = httpx.Response(
            200,
            json={"token_type": "bearer", "expires_in": 3600},
            request=_make_request(),
        )

        result = _request_token()

        assert result is None

    @patch("app.services.reddit_auth.settings")
    @patch("app.services.reddit_auth.httpx.post")
    def test_fetch_token_defaults_expires_in_to_3600(self, mock_post, mock_settings):
        """Should assume 3600s expiry if Reddit omits expires_in."""
        mock_settings.reddit_oauth_enabled = True
        mock_post.return_value = httpx.Response(
            200,
            json={"access_token": "tok", "token_type": "bearer"},
            request=_make_request(),
        )

        result = _request_token()

        assert result is not None
        _, expires_at = result
        expected_approx = time.time() + 3540  # 3600 - 60 safety margin
        assert abs(expires_at - expected_approx) < 2


# --- Cache hit / refresh tests ---


class TestGetRedditToken:
    @patch("app.services.reddit_auth.settings")
    @patch("app.services.reddit_auth._request_token")
    def test_cache_hit_no_refetch(self, mock_request, mock_settings):
        """Should return cached token without calling _request_token when not expired."""
        mock_settings.reddit_oauth_enabled = True
        reddit_auth._cached_token = "cached_tok"
        reddit_auth._expires_at = time.time() + 3000  # far in the future

        token = get_reddit_token()

        assert token == "cached_tok"
        mock_request.assert_not_called()

    @patch("app.services.reddit_auth.settings")
    @patch("app.services.reddit_auth._request_token")
    def test_refresh_when_expired(self, mock_request, mock_settings):
        """Should call _request_token when cached token has expired."""
        mock_settings.reddit_oauth_enabled = True
        reddit_auth._cached_token = "old_tok"
        reddit_auth._expires_at = time.time() - 100  # expired 100s ago
        mock_request.return_value = ("new_tok", time.time() + 3000)

        token = get_reddit_token()

        assert token == "new_tok"
        mock_request.assert_called_once()

    @patch("app.services.reddit_auth.settings")
    @patch("app.services.reddit_auth._request_token")
    def test_refresh_at_exact_expiry_boundary(self, mock_request, mock_settings):
        """Should refresh when now == _expires_at (treats expired as stale)."""
        mock_settings.reddit_oauth_enabled = True
        now = time.time()
        reddit_auth._cached_token = "boundary_tok"
        reddit_auth._expires_at = now  # exactly at boundary
        mock_request.return_value = ("fresh_tok", now + 3000)

        token = get_reddit_token()

        assert token == "fresh_tok"
        mock_request.assert_called_once()

    @patch("app.services.reddit_auth.settings")
    def test_returns_none_when_oauth_disabled(self, mock_settings):
        """Should return None when OAuth is not configured, without any HTTP calls."""
        mock_settings.reddit_oauth_enabled = False

        token = get_reddit_token()

        assert token is None

    @patch("app.services.reddit_auth.settings")
    @patch("app.services.reddit_auth._request_token")
    def test_returns_stale_token_on_refresh_failure(self, mock_request, mock_settings):
        """Should return the stale cached token if refresh fails, rather than None."""
        mock_settings.reddit_oauth_enabled = True
        reddit_auth._cached_token = "stale_but_ok"
        reddit_auth._expires_at = time.time() - 100  # expired
        mock_request.return_value = None  # refresh fails

        token = get_reddit_token()

        # Returns stale token as fallback
        assert token == "stale_but_ok"

    @patch("app.services.reddit_auth.settings")
    @patch("app.services.reddit_auth._request_token")
    def test_returns_none_when_no_cache_and_refresh_fails(self, mock_request, mock_settings):
        """Should return None when there's no cache and refresh fails."""
        mock_settings.reddit_oauth_enabled = True
        reddit_auth._cached_token = None
        reddit_auth._expires_at = 0.0
        mock_request.return_value = None

        token = get_reddit_token()

        assert token is None

    @patch("app.services.reddit_auth.settings")
    @patch("app.services.reddit_auth._request_token")
    def test_caches_new_token_after_refresh(self, mock_request, mock_settings):
        """Should update the module-level cache with the new token."""
        mock_settings.reddit_oauth_enabled = True
        reddit_auth._cached_token = None
        reddit_auth._expires_at = 0.0
        mock_request.return_value = ("brand_new", time.time() + 3000)

        token = get_reddit_token()

        assert token == "brand_new"
        assert reddit_auth._cached_token == "brand_new"
        assert reddit_auth._expires_at > time.time()


# --- Invalidate tests ---


class TestInvalidateToken:
    @patch("app.services.reddit_auth.settings")
    @patch("app.services.reddit_auth._request_token")
    def test_invalidate_forces_refetch(self, mock_request, mock_settings):
        """After invalidate_token(), next get_reddit_token() should fetch a fresh token."""
        mock_settings.reddit_oauth_enabled = True
        reddit_auth._cached_token = "old_cached"
        reddit_auth._expires_at = time.time() + 3000  # still valid

        invalidate_token()

        assert reddit_auth._cached_token is None
        assert reddit_auth._expires_at == 0.0

        mock_request.return_value = ("fresh_after_invalidate", time.time() + 3000)
        token = get_reddit_token()

        assert token == "fresh_after_invalidate"
        mock_request.assert_called_once()

    @patch("app.services.reddit_auth.settings")
    def test_invalidate_when_no_token(self, mock_settings):
        """Should be safe to call invalidate when there's no cached token."""
        mock_settings.reddit_oauth_enabled = True
        reddit_auth._cached_token = None
        reddit_auth._expires_at = 0.0

        # Should not raise
        invalidate_token()

        assert reddit_auth._cached_token is None
        assert reddit_auth._expires_at == 0.0

    @patch("app.services.reddit_auth.settings")
    @patch("app.services.reddit_auth._request_token")
    def test_invalidate_then_get_returns_new_token(self, mock_request, mock_settings):
        """Full cycle: get token → invalidate → get token should return different token."""
        mock_settings.reddit_oauth_enabled = True
        mock_request.return_value = ("first_token", time.time() + 3000)

        # First get caches "first_token"
        t1 = get_reddit_token()
        assert t1 == "first_token"

        invalidate_token()

        mock_request.return_value = ("second_token", time.time() + 3000)
        t2 = get_reddit_token()
        assert t2 == "second_token"

        assert mock_request.call_count == 2
