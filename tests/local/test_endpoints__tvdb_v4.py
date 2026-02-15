from mnamer.endpoints import tvdb_login, tvdb_search_series, tvdb_series_id


def test_tvdb_login__extracts_v4_data_token(monkeypatch):
    calls = []

    def mock_request_json(url, parameters=None, body=None, headers=None, cache=True):
        calls.append(
            {
                "url": url,
                "parameters": parameters,
                "body": body,
                "headers": headers,
                "cache": cache,
            }
        )
        return 200, {"status": "success", "data": {"token": "jwt-token"}}

    monkeypatch.setattr("mnamer.endpoints.request_json", mock_request_json)

    token = tvdb_login("api-key")

    assert token == "jwt-token"
    assert calls[0]["url"].endswith("/v4/login")
    assert calls[0]["body"] == {"apikey": "api-key"}
    assert calls[0]["cache"] is False


def test_tvdb_search_series__uses_bearer_and_normalizes(monkeypatch):
    observed_headers = {}

    def mock_request_json(url, parameters=None, body=None, headers=None, cache=True):
        observed_headers.update(headers or {})
        assert url.endswith("/v4/search")
        assert parameters["q"] == "The Rookie"
        return 200, {
            "status": "success",
            "data": [
                {"tvdb_id": 2001, "name": "The Rookie", "overview": "cop show"},
            ],
        }

    monkeypatch.setattr("mnamer.endpoints.request_json", mock_request_json)

    result = tvdb_search_series("token-123", series="The Rookie")

    assert observed_headers["Authorization"] == "Bearer token-123"
    assert result["data"][0]["id"] == 2001
    assert result["data"][0]["seriesName"] == "The Rookie"


def test_tvdb_search_series__normalizes_series_prefixed_ids(monkeypatch):
    def mock_request_json(url, parameters=None, body=None, headers=None, cache=True):
        assert url.endswith("/v4/search")
        return 200, {
            "status": "success",
            "data": [
                {"id": "series-446831", "name": "MobLand"},
            ],
        }

    monkeypatch.setattr("mnamer.endpoints.request_json", mock_request_json)

    result = tvdb_search_series("token-123", series="Mobland")
    assert result["data"][0]["id"] == "446831"
    assert result["data"][0]["seriesId"] == "446831"


def test_tvdb_series_id__uses_bearer_header(monkeypatch):
    observed_headers = {}

    def mock_request_json(url, parameters=None, body=None, headers=None, cache=True):
        observed_headers.update(headers or {})
        assert url.endswith("/v4/series/73739/extended")
        return 200, {"data": {"id": 73739, "name": "Lost"}}

    monkeypatch.setattr("mnamer.endpoints.request_json", mock_request_json)

    result = tvdb_series_id("token-abc", "73739")

    assert observed_headers["Authorization"] == "Bearer token-abc"
    assert result["data"]["id"] == 73739
    assert result["data"]["seriesName"] == "Lost"
