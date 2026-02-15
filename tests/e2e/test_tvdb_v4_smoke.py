import pytest

from mnamer.exceptions import MnamerNotFoundException

pytestmark = [pytest.mark.e2e]


@pytest.mark.usefixtures("setup_test_dir")
def test_tvdb_smoke_parse_search_lookup_and_format(e2e_run, setup_test_files, monkeypatch):
    setup_test_files("SeriesAlpha.S02E19.EpisodeTitle.mkv")

    def fake_tvdb_login(_api_key):
        return "jwt-token"

    def fake_tvdb_search_series(_token, series=None, **_kwargs):
        if series:
            return {"data": [{"id": 2001, "seriesName": "Series Alpha"}]}
        raise MnamerNotFoundException

    def fake_tvdb_series_id(_token, id_tvdb, **_kwargs):
        if str(id_tvdb) == "2001":
            return {"data": {"id": 2001, "seriesName": "Series Alpha"}}
        raise MnamerNotFoundException

    def fake_tvdb_series_id_episodes_query(
        _token,
        id_tvdb,
        episode=None,
        season=None,
        page=1,
        **_kwargs,
    ):
        if str(id_tvdb) != "2001" or page != 1:
            raise MnamerNotFoundException
        if season == 2 and episode == 19:
            return {
                "data": [
                    {
                        "firstAired": "2020-05-10",
                        "airedEpisodeNumber": 19,
                        "airedSeason": 2,
                        "overview": "Sample synopsis for testing.",
                        "episodeName": "Episode Title",
                        "id": 110381,
                    }
                ],
                "links": {"last": 1, "next": None, "prev": None},
            }
        raise MnamerNotFoundException

    monkeypatch.setattr("mnamer.providers.tvdb_login", fake_tvdb_login)
    monkeypatch.setattr("mnamer.providers.tvdb_search_series", fake_tvdb_search_series)
    monkeypatch.setattr("mnamer.providers.tvdb_series_id", fake_tvdb_series_id)
    monkeypatch.setattr(
        "mnamer.providers.tvdb_series_id_episodes_query",
        fake_tvdb_series_id_episodes_query,
    )

    result = e2e_run(
        "--test",
        "--batch",
        "--media=episode",
        "--episode-api=tvdb",
        "SeriesAlpha.S02E19.EpisodeTitle.mkv",
    )
    assert result.code == 0
    assert "Series Alpha - S02E19 - Episode Title.mkv" in result.out
    assert "1 out of 1 files processed successfully" in result.out
