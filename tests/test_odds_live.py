import pytest
import requests

from tennis_edge.ingest import odds_live

FAKE_KEY = "test-key-should-never-appear-0123456789"


class _Resp:
    ok, status_code = False, 401


def test_http_error_does_not_leak_key(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp())
    with pytest.raises(RuntimeError) as err:
        odds_live.tennis_sports(FAKE_KEY)
    assert FAKE_KEY not in str(err.value) and "401" in str(err.value)
    assert err.value.__cause__ is None and err.value.__context__ is None  # nothing chained


def test_network_error_does_not_leak_key(monkeypatch):
    def boom(url, params=None, **kw):
        raise requests.ConnectionError(f"failed for {url}?apiKey={params['apiKey']}")
    monkeypatch.setattr(requests, "get", boom)
    with pytest.raises(RuntimeError) as err:
        odds_live.fetch_odds(FAKE_KEY, "tennis_atp_x", "eu")
    assert FAKE_KEY not in str(err.value)
    assert err.value.__suppress_context__  # original message (with key) is not chained
