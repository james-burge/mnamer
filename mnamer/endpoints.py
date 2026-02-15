"""Provides a low-level interface for metadata media APIs."""

import datetime
from re import match
from time import sleep
from urllib.parse import parse_qs, urlparse

from mnamer.exceptions import (
    MnamerException,
    MnamerNetworkException,
    MnamerNotFoundException,
)
from mnamer.language import Language
from mnamer.utils import clean_dict, parse_date, request_json

OMDB_PLOT_TYPES = {"short", "long"}
MAX_RETRIES = 5
TVDB_V4_BASE = "https://api4.thetvdb.com/v4"


def omdb_title(
    api_key: str,
    id_imdb: str | None = None,
    media: str | None = None,
    title: str | None = None,
    season: int | None = None,
    episode: int | None = None,
    year: int | None = None,
    plot: str | None = None,
    cache: bool = True,
) -> dict:
    """
    Looks up media by id using the Open Movie Database.

    Online docs: http://www.omdbapi.com/#parameters
    """
    if (not title and not id_imdb) or (title and id_imdb):
        raise MnamerException("either id_imdb or title must be specified")
    elif plot and plot not in OMDB_PLOT_TYPES:
        raise MnamerException(f"plot must be one of {','.join(OMDB_PLOT_TYPES)}")
    url = "http://www.omdbapi.com"
    parameters = {
        "apikey": api_key,
        "i": id_imdb,
        "t": title,
        "y": year,
        "season": season,
        "episode": episode,
        "type": media,
        "plot": plot,
    }
    parameters = clean_dict(parameters)
    status, content = request_json(url, parameters, cache=cache)
    error = content.get("Error") if isinstance(content, dict) else None
    if status == 401:
        if error == "Request limit reached!":
            raise MnamerException("API request limit reached")
        raise MnamerException("invalid API key")
    elif status != 200 or not isinstance(content, dict):  # pragma: no cover
        raise MnamerNetworkException("OMDb down or unavailable?")
    elif error:
        raise MnamerNotFoundException(error)
    return content


def omdb_search(
    api_key: str,
    query: str,
    year: int | None = None,
    media: str | None = None,
    page: int = 1,
    cache: bool = True,
) -> dict:
    """
    Search for media using the Open Movie Database.

    Online docs: http://www.omdbapi.com/#parameters.
    """
    if page < 1 or page > 100:
        raise MnamerException("page must be between 1 and 100")
    url = "http://www.omdbapi.com"
    parameters = {
        "apikey": api_key,
        "s": query,
        "y": year,
        "type": media,
        "page": page,
    }
    parameters = clean_dict(parameters)
    status, content = request_json(url, parameters, cache=cache)
    if status == 401:
        raise MnamerException("invalid API key")
    elif content and not content.get("totalResults"):
        raise MnamerNotFoundException()
    elif not content or status != 200:  # pragma: no cover
        raise MnamerNetworkException("OMDb down or unavailable?")
    return content


def tmdb_find(
    api_key: str,
    external_source: str,
    external_id: str,
    language: Language | None = None,
    cache: bool = True,
) -> dict:
    """
    Search for The Movie Database objects using another DB's foreign key.

    Note: language codes aren't checked on this end or by TMDb, so if you
        enter an invalid language code your search itself will succeed, but
        certain fields like synopsis will just be empty.

    Online docs: developers.themoviedb.org/3/find.
    """
    sources = ["imdb_id", "freebase_mid", "freebase_id", "tvdb_id", "tvrage_id"]
    if external_source not in sources:
        raise MnamerException(f"external_source must be in {sources}")
    if external_source == "imdb_id" and not match(r"tt\d+", external_id):
        raise MnamerException("invalid imdb tt-const value")
    url = "https://api.themoviedb.org/3/find/" + external_id or ""
    parameters = {
        "api_key": api_key,
        "external_source": external_source,
        "language": language,
    }
    keys = [
        "movie_results",
        "person_results",
        "tv_episode_results",
        "tv_results",
        "tv_season_results",
    ]
    status, content = request_json(url, parameters, cache=cache)
    if status == 401:
        raise MnamerException("invalid API key")
    elif status != 200 or not any(content.keys()):  # pragma: no cover
        raise MnamerNetworkException("TMDb down or unavailable?")
    elif status == 404 or not any(content.get(k, {}) for k in keys):
        raise MnamerNotFoundException
    return content


def tmdb_movies(
    api_key: str,
    id_tmdb: str,
    language: Language | None = None,
    cache: bool = True,
) -> dict:
    """
    Lookup a movie item using The Movie Database.

    Online docs: developers.themoviedb.org/3/movies.
    """
    url = f"https://api.themoviedb.org/3/movie/{id_tmdb}"
    parameters = {"api_key": api_key, "language": language}
    status, content = request_json(url, parameters, cache=cache)
    if status == 401:
        raise MnamerException("invalid API key")
    elif status == 404:
        raise MnamerNotFoundException
    elif status != 200 or not any(content.keys()):  # pragma: no cover
        raise MnamerNetworkException("TMDb down or unavailable?")
    return content


def tmdb_search_movies(
    api_key: str,
    title: str,
    year: int | str | None = None,
    language: Language | None = None,
    region: str | None = None,
    adult: bool = False,
    page: int = 1,
    cache: bool = True,
) -> dict:
    """
    Search for movies using The Movie Database.

    Online docs: developers.themoviedb.org/3/search/search-movies.
    """
    url = "https://api.themoviedb.org/3/search/movie"
    parameters = {
        "api_key": api_key,
        "query": title,
        "page": page,
        "include_adult": adult,
        "language": language,
        "region": region,
        "year": year,
    }
    status, content = request_json(url, parameters, cache=cache)
    if status == 401:
        raise MnamerException("invalid API key")
    elif status != 200 or not any(content.keys()):  # pragma: no cover
        raise MnamerNetworkException("TMDb down or unavailable?")
    elif status == 404 or status == 422 or not content.get("total_results"):
        raise MnamerNotFoundException
    return content


def tvdb_login(api_key: str | None) -> str:
    """
    Logs into TVDb using the provided api key.

    Note: You can register for a free TVDb key at thetvdb.com/?tab=apiregister
    """
    body = {"apikey": api_key}
    status, content = tvdb_request_json("/login", body=body, cache=False)
    data = tvdb_v4_data(content)
    token = data.get("token") if isinstance(data, dict) else None
    if status in (401, 403):
        raise MnamerException("invalid api key")
    elif status != 200 or not token:  # pragma: no cover
        raise MnamerNetworkException("TVDb down or unavailable?")
    return token


def tvdb_refresh_token(token: str) -> str:
    """
    Refreshes JWT token.

    Online docs: https://api4.thetvdb.com/v4.
    """
    status, content = tvdb_request_json("/refresh_token", token=token, cache=False)
    data = tvdb_v4_data(content)
    refreshed = data.get("token") if isinstance(data, dict) else None
    if status == 401:
        raise MnamerException("invalid token")
    elif status in (404, 405):
        return token
    elif status != 200 or not refreshed:  # pragma: no cover
        raise MnamerNetworkException("TVDb down or unavailable?")
    return refreshed


def tvdb_episodes_id(
    token: str,
    id_tvdb: str,
    language: Language | None = None,
    cache: bool = True,
) -> dict:
    """
    Returns the full information for a given episode id.

    Online docs: https://api4.thetvdb.com/v4.
    """
    Language.ensure_valid_for_tvdb(language)
    _ensure_numeric_id(id_tvdb, "id_tvdb")

    for path in (f"/episodes/{id_tvdb}/extended", f"/episodes/{id_tvdb}"):
        status, content = tvdb_request_json(
            path,
            token=token,
            language=language,
            cache=cache,
        )
        if status == 401:
            raise MnamerException("invalid token")
        if status == 429:
            raise MnamerNetworkException("TVDb rate limited, try again later")
        if status == 404:
            continue
        if status != 200:
            raise MnamerNetworkException("TVDb down or unavailable?")
        payload = _tvdb_normalize_episode_entry(tvdb_v4_data(content))
        if not payload:
            raise MnamerNotFoundException
        return {"data": payload}
    raise MnamerNotFoundException


def tvdb_series_id(
    token: str,
    id_tvdb: str,
    language: Language | None = None,
    cache: bool = True,
) -> dict:
    """
    Returns a series records that contains all information known about a
    particular series id.

    Online docs: https://api4.thetvdb.com/v4.
    """
    Language.ensure_valid_for_tvdb(language)
    _ensure_numeric_id(id_tvdb, "id_tvdb")

    for path in (f"/series/{id_tvdb}/extended", f"/series/{id_tvdb}"):
        status, content = tvdb_request_json(
            path,
            token=token,
            language=language,
            cache=cache,
        )
        if status == 401:
            raise MnamerException("invalid token")
        if status == 429:
            raise MnamerNetworkException("TVDb rate limited, try again later")
        if status == 404:
            continue
        if status != 200:
            raise MnamerNetworkException("TVDb down or unavailable?")
        payload = _tvdb_normalize_series_entry(tvdb_v4_data(content))
        if not payload:
            raise MnamerNotFoundException
        return {"data": payload}
    raise MnamerNotFoundException


def tvdb_series_id_episodes(
    token: str,
    id_tvdb: str,
    page: int = 1,
    language: Language | None = None,
    cache: bool = True,
) -> dict:
    """
    All episodes for a given series.

    Note: Paginated with up to 100 results per page.
    Online docs: https://api4.thetvdb.com/v4.
    """
    Language.ensure_valid_for_tvdb(language)
    _ensure_numeric_id(id_tvdb, "id_tvdb")
    if page < 1:
        raise MnamerException("page must be greater than or equal to 1")

    attempts = [
        (f"/series/{id_tvdb}/episodes/default", {"page": page}),
        (f"/series/{id_tvdb}/episodes/official", {"page": page}),
        (f"/series/{id_tvdb}/episodes", {"page": page}),
    ]
    status, content = _tvdb_request_first_available(
        token=token,
        language=language,
        cache=cache,
        attempts=attempts,
    )
    if status == 401:
        raise MnamerException("invalid token")
    if status == 429:
        raise MnamerNetworkException("TVDb rate limited, try again later")
    if status == 404:
        raise MnamerNotFoundException
    if status != 200:
        raise MnamerNetworkException("TVDb down or unavailable?")

    data = _tvdb_normalize_episode_list(tvdb_v4_data(content))
    if not data:
        raise MnamerNotFoundException
    return {"data": data, "links": _tvdb_normalize_links(content.get("links"), page)}


def tvdb_series_id_episodes_query(
    token: str,
    id_tvdb: str,
    episode: int | None = None,
    season: int | None = None,
    page: int = 1,
    language: Language | None = None,
    cache: bool = True,
) -> dict:
    """
    Allows the user to query against episodes for the given series.

    Note: Paginated with up to 100 results per page.
    Online docs: https://api4.thetvdb.com/v4.
    """
    Language.ensure_valid_for_tvdb(language)
    _ensure_numeric_id(id_tvdb, "id_tvdb")
    if page < 1:
        raise MnamerException("page must be greater than or equal to 1")

    parameters = {"page": page, "season": season, "episodeNumber": episode}
    attempts = [
        (f"/series/{id_tvdb}/episodes/default", parameters),
        (f"/series/{id_tvdb}/episodes/official", parameters),
        (
            f"/series/{id_tvdb}/episodes/query",
            {"page": page, "airedSeason": season, "airedEpisode": episode},
        ),
    ]

    status, content = _tvdb_request_first_available(
        token=token,
        language=language,
        cache=cache,
        attempts=attempts,
    )
    if status == 401:
        raise MnamerException("invalid token")
    if status == 429:
        raise MnamerNetworkException("TVDb rate limited, try again later")
    if status == 404:
        raise MnamerNotFoundException
    if status != 200:
        raise MnamerNetworkException("TVDb down or unavailable?")

    data = _tvdb_normalize_episode_list(tvdb_v4_data(content))
    if not data:
        raise MnamerNotFoundException
    return {"data": data, "links": _tvdb_normalize_links(content.get("links"), page)}


def tvdb_search_series(
    token: str,
    series: str | None = None,
    id_imdb: str | None = None,
    id_zap2it: str | None = None,
    language: Language | None = None,
    cache: bool = True,
) -> dict:
    """
    Allows the user to search for a series based on the following parameters.

    Online docs: https://api4.thetvdb.com/v4.
    """
    Language.ensure_valid_for_tvdb(language)
    if not any((series, id_imdb, id_zap2it)):
        raise MnamerException("one of series, id_imdb, id_zap2it must be specified")
    if sum(1 for v in (series, id_imdb, id_zap2it) if v) > 1:
        raise MnamerException(
            "series, id_imdb, id_zap2it parameters are mutually exclusive"
        )
    if id_imdb and not match(r"tt\d+", id_imdb):
        raise MnamerException("invalid imdb tt-const value")

    query_value = series or id_imdb or id_zap2it
    assert query_value
    attempts = [
        ("/search", {"q": query_value, "query": query_value, "type": "series"}),
    ]
    if id_imdb:
        attempts.append((f"/search/remoteid/{id_imdb}", None))
    elif id_zap2it:
        attempts.append((f"/search/remoteid/{id_zap2it}", None))

    status, content = _tvdb_request_first_available(
        token=token,
        language=language,
        cache=cache,
        attempts=attempts,
    )
    if status == 401:
        raise MnamerException("invalid token")
    elif status == 429:
        raise MnamerNetworkException("TVDb rate limited, try again later")
    elif status == 404:
        raise MnamerNotFoundException
    elif status != 200:  # pragma: no cover
        raise MnamerNetworkException("TVDb down or unavailable?")

    data = tvdb_v4_data(content)
    if isinstance(data, dict):
        results = [data]
    elif isinstance(data, list):
        results = data
    else:
        results = []

    normalized = [_tvdb_normalize_series_entry(entry) for entry in results]
    normalized = [entry for entry in normalized if entry]
    if not normalized:
        raise MnamerNotFoundException
    return {"data": normalized}


def tvdb_request_json(
    path: str,
    token: str | None = None,
    params: dict | None = None,
    body: dict | None = None,
    language: Language | None = None,
    cache: bool = True,
) -> tuple[int, dict]:
    """Wrapper for TVDb v4 requests."""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if language:
        headers["Accept-Language"] = language.a2
    return request_json(
        f"{TVDB_V4_BASE}{path}",
        parameters=params,
        body=body,
        headers=headers,
        cache=cache is True and language is None,
    )


def tvdb_v4_data(content: dict) -> dict | list:
    """Extracts v4 `data` payloads while tolerating malformed responses."""
    if not isinstance(content, dict):
        return {}
    return content.get("data") or {}


def _ensure_numeric_id(value: str, parameter_name: str) -> None:
    if not str(value).isdigit():
        raise MnamerException(f"invalid {parameter_name}")


def _tvdb_request_first_available(
    token: str,
    language: Language | None,
    cache: bool,
    attempts: list[tuple[str, dict | None]],
) -> tuple[int, dict]:
    """
    Returns the first non-404/405 response from a list of TVDb request attempts.
    """
    fallback = (404, {})
    for path, params in attempts:
        status, content = tvdb_request_json(
            path,
            token=token,
            params=params,
            language=language,
            cache=cache,
        )
        if status in (404, 405):
            fallback = (status, content)
            continue
        return status, content
    return fallback


def _tvdb_extract_page(value: int | str | None) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if value.isdigit():
            return int(value)
        parsed = parse_qs(urlparse(value).query)
        page = parsed.get("page", [None])[0]
        if page and str(page).isdigit():
            return int(page)
    return None


def _tvdb_normalize_links(links: dict | None, page: int) -> dict:
    links = links if isinstance(links, dict) else {}
    prev_page = _tvdb_extract_page(links.get("prev"))
    next_page = _tvdb_extract_page(links.get("next"))
    last_page = _tvdb_extract_page(links.get("last"))
    if last_page is None and next_page is not None:
        last_page = max(page, next_page)
    if last_page is None:
        last_page = page
    return {
        "first": 1,
        "last": last_page,
        "next": next_page,
        "prev": prev_page,
    }


def _tvdb_normalize_series_entry(entry: dict | None) -> dict | None:
    if not isinstance(entry, dict):
        return None
    series_id = _tvdb_extract_numeric_id(
        entry.get("tvdb_id")
        or entry.get("tvdbId")
        or entry.get("id")
        or entry.get("objectID")
    )
    if series_id in (None, ""):
        return None
    name = entry.get("seriesName") or entry.get("name")
    return {
        "aliases": entry.get("aliases") or [],
        "banner": entry.get("banner"),
        "firstAired": entry.get("firstAired") or entry.get("first_air_time"),
        "id": series_id,
        "image": entry.get("image"),
        "network": entry.get("network"),
        "overview": entry.get("overview"),
        "poster": entry.get("poster"),
        "seriesId": series_id,
        "seriesName": name,
        "slug": entry.get("slug"),
        "status": entry.get("status"),
    }


def _tvdb_normalize_episode_entry(entry: dict | None) -> dict | None:
    if not isinstance(entry, dict):
        return None
    episode_id = _tvdb_extract_numeric_id(entry.get("id"))
    if episode_id in (None, "", 0):
        return None
    return {
        "airedEpisodeNumber": entry.get("airedEpisodeNumber")
        or entry.get("number")
        or entry.get("episodeNumber"),
        "airedSeason": entry.get("airedSeason")
        or entry.get("seasonNumber")
        or entry.get("season"),
        "episodeName": entry.get("episodeName") or entry.get("name"),
        "firstAired": entry.get("firstAired")
        or entry.get("aired")
        or entry.get("airedDate"),
        "id": episode_id,
        "overview": entry.get("overview"),
        "seriesId": entry.get("seriesId") or entry.get("series_id"),
    }


def _tvdb_normalize_episode_list(data: dict | list) -> list[dict]:
    if isinstance(data, dict):
        data = data.get("episodes") or [data]
    if not isinstance(data, list):
        return []
    episodes = [_tvdb_normalize_episode_entry(entry) for entry in data]
    return [entry for entry in episodes if entry]


def _tvdb_extract_numeric_id(value: int | str | None) -> int | str | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if value.isdigit():
            return value
        parts = value.split("-")
        if parts and parts[-1].isdigit():
            return parts[-1]
    return value


def tvmaze_show(
    id_tvmaze: str,
    embed_episodes: bool = False,
    cache: bool = False,
    attempt: int = 1,
):
    """
    Retrieve all primary information for a given show.

    Online docs: https://www.tvmaze.com/api#show-main-information
    """
    url = f"http://api.tvmaze.com/shows/{id_tvmaze}"
    parameters = {}
    if embed_episodes:
        parameters["embed"] = "episodes"
    status, content = request_json(url, parameters, cache=cache)
    if status == 443 and attempt <= MAX_RETRIES:  # pragma: no cover
        sleep(attempt * 2)
        return tvmaze_show(id_tvmaze, embed_episodes, cache, attempt + 1)
    elif status == 404 or not content:
        raise MnamerNotFoundException
    elif status != 200:  # pragma: no cover
        raise MnamerNetworkException
    return content


def tvmaze_show_search(query: str, cache: bool = True, attempt: int = 1) -> dict:
    """
    Search through all the shows in the database by the show's name. A fuzzy
    algorithm is used (with a fuzziness value of 2), meaning that shows will be
    found even if your query contains small typos. Results are returned in order
    of relevancy (best matches on top) and contain each show's full information.

    Online docs: https://www.tvmaze.com/api#show-search
    """
    url = "http://api.tvmaze.com/search/shows"
    parameters = {"q": query}
    status, content = request_json(url, parameters, cache=cache)
    if status == 443 and attempt <= MAX_RETRIES:  # pragma: no cover
        sleep(attempt * 2)
        return tvmaze_show_search(query, cache, attempt + 1)
    elif status == 404 or not content:
        raise MnamerNotFoundException
    elif status != 200:  # pragma: no cover
        raise MnamerNetworkException
    return content


def tvmaze_show_single_search(query: str, cache: bool = True, attempt: int = 1) -> dict:
    """
    Singlesearch endpoint either returns exactly one result, or no result at
    all. This endpoint is also forgiving of typos, but less so than the regular
    search (with a fuzziness of 1 instead of 2), to reduce the chance of a false
    positive.

    Online docs: https://www.tvmaze.com/api#show-single-search
    """
    url = "http://api.tvmaze.com/singlesearch/shows"
    parameters = {"q": query}
    status, content = request_json(url, parameters, cache=cache)
    if status == 443 and attempt <= MAX_RETRIES:  # pragma: no cover
        sleep(attempt * 2)
        return tvmaze_show_single_search(query, cache, attempt + 1)
    elif status == 404 or not content:
        raise MnamerNotFoundException
    elif status != 200:  # pragma: no cover
        raise MnamerNetworkException
    return content


def tvmaze_show_lookup(
    id_imdb: str | None = None,
    id_tvdb: str | None = None,
    cache: bool = True,
    attempt: int = 1,
) -> dict:
    """
    If you already know a show's tvrage, thetvdb or IMDB ID, you can use this
    endpoint to find this exact show on TVmaze.

    Online docs: https://www.tvmaze.com/api#show-lookup
    """
    if not [id_imdb, id_tvdb].count(None) == 1:
        raise MnamerException("id_imdb and id_tvdb are mutually exclusive")
    url = "http://api.tvmaze.com/lookup/shows"
    parameters = {"imdb": id_imdb, "thetvdb": id_tvdb}
    status, content = request_json(url, parameters, cache=cache)
    if status == 443 and attempt <= MAX_RETRIES:  # pragma: no cover
        sleep(attempt * 2)
        return tvmaze_show_lookup(id_imdb, id_tvdb, cache, attempt + 1)
    elif status == 404:
        raise MnamerNotFoundException
    elif status != 200 or not content:  # pragma: no cover
        raise MnamerNetworkException
    return content


def tvmaze_show_episodes_list(
    id_tvmaze: str,
    include_specials: bool = False,
    cache: bool = True,
    attempt: int = 1,
) -> dict:
    """
    A complete list of episodes for the given show. Episodes are returned in
    their airing order, and include full episode information. By default,
    specials are not included in the list.

    Online docs: https://www.tvmaze.com/api#show-episode-list
    """
    url = f"http://api.tvmaze.com/shows/{id_tvmaze}/episodes"
    parameters = {"specials": int(include_specials)}
    status, content = request_json(url, parameters, cache=cache)
    if status == 443 and attempt <= MAX_RETRIES:  # pragma: no cover
        sleep(attempt * 2)
        return tvmaze_show_episodes_list(
            id_tvmaze, include_specials, cache, attempt + 1
        )
    elif status == 404:
        raise MnamerNotFoundException
    elif status != 200 or not content:  # pragma: no cover
        raise MnamerNetworkException
    return content


def tvmaze_episodes_by_date(
    id_tvmaze: str,
    air_date: datetime.date | str,
    cache: bool = True,
    attempt: int = 1,
) -> dict:
    """
    Retrieves all episodes from this show that have aired on a specific date.
    Useful for daily shows that don't adhere to a common season numbering.

    Online docs: https://www.tvmaze.com/api#episodes-by-date
    """
    url = f"http://api.tvmaze.com/shows/{id_tvmaze}/episodesbydate"
    parameters = {"date": parse_date(air_date)}
    status, content = request_json(url, parameters, cache=cache)
    if status == 443 and attempt <= MAX_RETRIES:  # pragma: no cover
        sleep(attempt * 2)
        return tvmaze_episodes_by_date(id_tvmaze, air_date, cache, attempt + 1)
    elif status == 404:
        raise MnamerNotFoundException
    elif status != 200 or not content:  # pragma: no cover
        raise MnamerNetworkException
    return content


def tvmaze_episode_by_number(
    id_tvmaze: str,
    season: int | None,
    episode: int | None,
    cache: bool = True,
    attempt: int = 1,
) -> dict:
    """
    Retrieve one specific episode from this show given its season number and
    episode number.

    Online docs: https://www.tvmaze.com/api#episode-by-number
    """
    url = f"http://api.tvmaze.com/shows/{id_tvmaze}/episodebynumber"
    parameters = {"season": season, "number": episode}
    status, content = request_json(url, parameters, cache=cache)
    if status == 443 and attempt <= MAX_RETRIES:  # pragma: no cover
        sleep(attempt * 2)
        return tvmaze_episode_by_number(id_tvmaze, season, episode, cache, attempt + 1)
    elif status == 404:
        raise MnamerNotFoundException
    elif status != 200 or not content:  # pragma: no cover
        raise MnamerNetworkException
    return content
